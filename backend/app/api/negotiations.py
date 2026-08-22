"""Negotiation API endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.graph.negotiation_graph import run_negotiation
from app.models.database_models import (
    AgreementDB,
    CostTrackingDB,
    NegotiationDB,
    NegotiationEventDB,
    OfferDB,
    PartyDB,
    PropertyDB,
)
from app.models.schemas import (
    ApprovalRequest,
    CreateNegotiationRequest,
    NegotiationScenario,
    NegotiationStatus,
    PartyRole,
    StructuredOffer,
    PropertyCreate,
)
from app.negotiation.engine import get_all_scenarios, get_scenario
from app.negotiation.scorer import NegotiationScorer
from app.services.event_service import get_event_service

logger = structlog.get_logger()
router = APIRouter(prefix="/api")


# ═══════════════════════════════════════════════════════════════════════════
# Properties (Marketplace)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/properties")
async def list_properties(host_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """List properties in the marketplace."""
    query = select(PropertyDB).order_by(PropertyDB.created_at.desc())
    if host_id:
        query = query.where(PropertyDB.host_id == host_id)
    result = await db.execute(query)
    properties = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "location": p.location,
            "property_type": p.property_type,
            "bedrooms": p.bedrooms,
            "beds": p.beds,
            "bathrooms": p.bathrooms,
            "amenities": p.amenities,
            "base_price": p.base_price,
            "currency": p.currency,
            "images": p.images,
            "rating": p.rating,
            "review_count": p.review_count,
            # We explicitly do NOT return negotiation_config here to keep it private!
        }
        for p in properties
    ]


@router.post("/properties")
async def create_property(req: PropertyCreate, db: AsyncSession = Depends(get_db)):
    """Create a new property."""
    p_db = PropertyDB(
        host_id=req.host_id,
        title=req.title,
        description=req.description,
        location=req.location,
        property_type=req.property_type,
        bedrooms=req.bedrooms,
        beds=req.beds,
        bathrooms=req.bathrooms,
        base_price=req.base_price,
        currency=req.currency,
        cleaning_fee=req.cleaning_fee,
        deposit=req.deposit,
        minimum_stay=req.minimum_stay,
        maximum_stay=req.maximum_stay,
    )
    p_db.images = req.images
    p_db.amenities = req.amenities
    p_db.negotiation_config = req.negotiation_config
    
    db.add(p_db)
    await db.commit()
    
    return {"id": p_db.id, "message": "Property created successfully"}


@router.get("/properties/{property_id}")
async def get_property(property_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single property by ID."""
    result = await db.execute(select(PropertyDB).where(PropertyDB.id == property_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
        
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "location": p.location,
        "property_type": p.property_type,
        "bedrooms": p.bedrooms,
        "beds": p.beds,
        "bathrooms": p.bathrooms,
        "amenities": p.amenities,
        "base_price": p.base_price,
        "currency": p.currency,
        "cleaning_fee": p.cleaning_fee,
        "deposit": p.deposit,
        "minimum_stay": p.minimum_stay,
        "maximum_stay": p.maximum_stay,
        "images": p.images,
        "rating": p.rating,
        "review_count": p.review_count,
    }


@router.get("/properties/{property_id}/negotiations")
async def get_property_negotiations(property_id: str, db: AsyncSession = Depends(get_db)):
    """Get all negotiations for a specific property."""
    query = (
        select(NegotiationDB)
        .where(NegotiationDB.property_id == property_id)
        .options(selectinload(NegotiationDB.parties))
        .order_by(NegotiationDB.updated_at.desc())
    )
    result = await db.execute(query)
    negotiations = result.scalars().all()
    
    return [
        {
            "id": n.id,
            "status": n.status,
            "current_round": n.current_round,
            "guest_name": next((p.name for p in n.parties if p.role == "party_a"), "Guest"),
            "host_name": next((p.name for p in n.parties if p.role == "party_b"), "Host"),
            "created_at": str(n.created_at),
            "updated_at": str(n.updated_at),
        }
        for n in negotiations
    ]


@router.post("/properties/{property_id}/negotiate")
async def start_property_negotiation(
    property_id: str, 
    req: dict, # Expecting just {"party_a_preferences": {...}}
    db: AsyncSession = Depends(get_db)
):
    """Start a negotiation for a specific property."""
    # 1. Get the property (which has the hidden host preferences)
    result = await db.execute(select(PropertyDB).where(PropertyDB.id == property_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
        
    party_a_prefs = req.get("party_a_preferences", {})
    party_b_prefs = p.negotiation_config
    
    # 2. Create the NegotiationDB
    neg_db = NegotiationDB(
        property_id=p.id,
        scenario="rental",
        status="pending",
    )
    neg_db.config = {
        "scenario": "rental",
        "max_rounds": 10,
        "party_a_name": "Guest",
        "party_b_name": "Host",
        "property_id": p.id,
        "property_title": p.title,
    }
    db.add(neg_db)
    
    # 3. Create Parties
    party_a = PartyDB(negotiation=neg_db, role="party_a", name="Guest")
    party_a.preferences = party_a_prefs
    db.add(party_a)

    party_b = PartyDB(negotiation=neg_db, role="party_b", name="Host")
    party_b.preferences = party_b_prefs
    db.add(party_b)
    
    # Update status to in_progress
    neg_db.status = "in_progress"
    
    await db.commit()
    
    # 4. Prepare initial state and auto-start the negotiation graph in the background
    neg_id = neg_db.id
    
    initial_state = {
        "negotiation_id": neg_id,
        "scenario": "rental",
        "max_rounds": 10,
        "party_a_name": "Guest",
        "party_b_name": "Host",
        "party_a_preferences": party_a_prefs,
        "party_b_preferences": party_b_prefs,
        "current_round": 0,
        "active_party": "party_a",
        "status": "in_progress",
        "offers_history": [],
        "events": [],
        "cost_metrics": [],
        "validation_retries": 0,
    }

    event_service = get_event_service()
    
    async def _run():
        try:
            from app.graph.negotiation_graph import get_compiled_graph
            graph = get_compiled_graph()

            from app.database import async_session_factory
            from app.models.database_models import OfferDB, NegotiationEventDB, CostTrackingDB, AgreementDB
            from app.models.schemas import StructuredOffer, NegotiationStatus
            import json
            
            saved_offers = 0
            saved_events = 0
            saved_costs = 0
            
            async for current_state in graph.astream(initial_state, stream_mode="values", config={"recursion_limit": 150}):
                async with async_session_factory() as session:
                    neg = await session.get(NegotiationDB, neg_id)
                    if not neg:
                        break
                        
                    # 1. Store NEW offers
                    offers = current_state.get("offers_history", [])
                    while saved_offers < len(offers):
                        offer_dict = offers[saved_offers]
                        offer = StructuredOffer(**offer_dict)
                        offer_db = OfferDB(
                            negotiation_id=neg_id,
                            round_number=offer.round,
                            party_role=offer.party.value,
                            terms_json=json.dumps(offer.terms, default=str),
                            reasoning=offer.reasoning_summary,
                            concessions_json=json.dumps(offer.concessions),
                            requested_concessions_json=json.dumps(offer.requested_concessions),
                            validation_result="valid",
                        )
                        session.add(offer_db)
                        saved_offers += 1
                        
                    # 2. Store NEW events & Publish via SSE
                    events = current_state.get("events", [])
                    while saved_events < len(events):
                        evt = events[saved_events]
                        evt_db = NegotiationEventDB(
                            negotiation_id=neg_id,
                            event_type=evt.get("event_type", ""),
                            round_number=evt.get("round", 0),
                            data_json=json.dumps(evt.get("data", {}), default=str),
                        )
                        session.add(evt_db)
                        await event_service.publish(neg_id, evt)
                        saved_events += 1
                        
                    # 3. Store NEW cost metrics
                    costs = current_state.get("cost_metrics", [])
                    while saved_costs < len(costs):
                        cost = costs[saved_costs]
                        cost_db = CostTrackingDB(
                            negotiation_id=neg_id,
                            round_number=cost.get("round", 0),
                            input_tokens=cost.get("input_tokens", 0),
                            output_tokens=cost.get("output_tokens", 0),
                            estimated_cost=cost.get("estimated_cost", 0.0),
                            latency_ms=cost.get("latency_ms", 0.0),
                            model=cost.get("model", ""),
                        )
                        session.add(cost_db)
                        saved_costs += 1
                        
                    # 4. Store agreement if present
                    agreement = current_state.get("agreement")
                    if agreement and neg.status != "awaiting_approval":
                        agreement_db = AgreementDB(
                            negotiation_id=neg_id,
                            final_terms_json=json.dumps(agreement.get("final_terms", {}), default=str),
                            party_a_satisfaction=agreement.get("party_a_satisfaction", 0),
                            party_b_satisfaction=agreement.get("party_b_satisfaction", 0),
                            fairness_score=agreement.get("fairness_score", 0),
                            constraint_violations=agreement.get("constraint_violations", 0),
                            total_rounds=agreement.get("total_rounds", 0),
                        )
                        session.add(agreement_db)
                        
                    # 5. Update status
                    neg.status = current_state.get("status", "failed")
                    neg.current_round = current_state.get("current_round", 0)
                    
                    await session.commit()
            
            await event_service.close_negotiation(neg_id)

        except Exception as e:
            logger.error("negotiation_run_failed", id=neg_id, error=str(e))
            try:
                from app.database import async_session_factory
                async with async_session_factory() as session:
                    neg = await session.get(NegotiationDB, neg_id)
                    if neg:
                        neg.status = "failed"
                        await session.commit()
                    await event_service.publish(neg_id, {
                        "event_type": "NEGOTIATION_FAILED",
                        "data": {"error": str(e)},
                    })
                    await event_service.close_negotiation(neg_id)
            except Exception:
                pass

    asyncio.create_task(_run())
    
    return {"id": neg_id, "status": "started"}


# ═══════════════════════════════════════════════════════════════════════════
# Scenarios
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/scenarios")
async def list_scenarios():
    """List all available negotiation scenarios."""
    scenarios = get_all_scenarios()
    return [
        {
            "name": s.name.value,
            "display_name": s.display_name,
            "description": s.description,
            "party_a_label": s.party_a_label,
            "party_b_label": s.party_b_label,
            "variables": [v.model_dump() for v in s.variables],
        }
        for s in scenarios
    ]


@router.get("/scenarios/{name}/defaults")
async def get_scenario_defaults(name: str):
    """Get default/seed preferences for a scenario."""
    try:
        scenario = NegotiationScenario(name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Scenario '{name}' not found")

    meta = get_scenario(scenario)
    return {
        "scenario": meta.name.value,
        "display_name": meta.display_name,
        "party_a_label": meta.party_a_label,
        "party_b_label": meta.party_b_label,
        "variables": [v.model_dump() for v in meta.variables],
        "default_party_a": meta.default_party_a.model_dump() if meta.default_party_a else None,
        "default_party_b": meta.default_party_b.model_dump() if meta.default_party_b else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Negotiations CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/negotiations")
async def create_negotiation(
    request: CreateNegotiationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new negotiation session."""
    settings = get_settings()

    # Create negotiation
    negotiation = NegotiationDB(
        scenario=request.config.scenario.value,
        status=NegotiationStatus.PENDING.value,
        config_json=json.dumps(request.config.model_dump(), default=str),
    )
    db.add(negotiation)
    await db.flush()

    # Create parties — preferences stored privately
    party_a = PartyDB(
        negotiation_id=negotiation.id,
        role=PartyRole.PARTY_A.value,
        name=request.config.party_a_name,
        preferences_json=json.dumps(request.party_a_preferences.model_dump(), default=str),
    )
    party_b = PartyDB(
        negotiation_id=negotiation.id,
        role=PartyRole.PARTY_B.value,
        name=request.config.party_b_name,
        preferences_json=json.dumps(request.party_b_preferences.model_dump(), default=str),
    )
    db.add(party_a)
    db.add(party_b)
    await db.flush()

    logger.info("negotiation_created", id=negotiation.id, scenario=negotiation.scenario)

    return {
        "id": negotiation.id,
        "scenario": negotiation.scenario,
        "status": negotiation.status,
        "party_a_name": request.config.party_a_name,
        "party_b_name": request.config.party_b_name,
        "max_rounds": request.config.max_rounds,
        "created_at": str(negotiation.created_at),
    }


@router.get("/negotiations/{negotiation_id}")
async def get_negotiation(
    negotiation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full negotiation details including offer history."""
    result = await db.execute(
        select(NegotiationDB)
        .where(NegotiationDB.id == negotiation_id)
        .options(
            selectinload(NegotiationDB.parties),
            selectinload(NegotiationDB.offers),
            selectinload(NegotiationDB.events),
            selectinload(NegotiationDB.agreement),
            selectinload(NegotiationDB.cost_records),
        )
    )
    negotiation = result.scalar_one_or_none()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    config = negotiation.config
    parties = {p.role: p for p in negotiation.parties}

    # Build offers list
    offers = []
    for o in negotiation.offers:
        offers.append({
            "round": o.round_number,
            "party": o.party_role,
            "party_name": parties.get(o.party_role, PartyDB()).name if o.party_role in parties else o.party_role,
            "terms": o.terms,
            "reasoning": o.reasoning,
            "concessions": o.concessions,
            "requested_concessions": o.requested_concessions,
            "validation_result": o.validation_result,
            "created_at": str(o.created_at),
        })

    # Build events list
    events = []
    for e in negotiation.events:
        events.append({
            "event_type": e.event_type,
            "round": e.round_number,
            "data": e.data,
            "timestamp": str(e.timestamp),
        })

    # Build cost summary
    total_input = sum(c.input_tokens for c in negotiation.cost_records)
    total_output = sum(c.output_tokens for c in negotiation.cost_records)
    total_cost = sum(c.estimated_cost for c in negotiation.cost_records)
    total_calls = len(negotiation.cost_records)
    avg_latency = (
        sum(c.latency_ms for c in negotiation.cost_records) / total_calls
        if total_calls
        else 0
    )
    models_used = list(set(c.model for c in negotiation.cost_records if c.model))

    # Agreement
    agreement_data = None
    if negotiation.agreement:
        a = negotiation.agreement
        agreement_data = {
            "final_terms": a.final_terms,
            "party_a_satisfaction": a.party_a_satisfaction,
            "party_b_satisfaction": a.party_b_satisfaction,
            "fairness_score": a.fairness_score,
            "constraint_violations": a.constraint_violations,
            "total_rounds": a.total_rounds,
            "party_a_approved": a.party_a_approved,
            "party_b_approved": a.party_b_approved,
            "rejection_reason": a.rejection_reason,
        }

    return {
        "id": negotiation.id,
        "scenario": negotiation.scenario,
        "status": negotiation.status,
        "config": config,
        "party_a_name": parties.get("party_a", PartyDB(name="Party A")).name,
        "party_b_name": parties.get("party_b", PartyDB(name="Party B")).name,
        "current_round": negotiation.current_round,
        "offers": offers,
        "events": events,
        "agreement": agreement_data,
        "cost_summary": {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_estimated_cost": round(total_cost, 6),
            "total_llm_calls": total_calls,
            "average_latency_ms": round(avg_latency, 1),
            "models_used": models_used,
        },
        "created_at": str(negotiation.created_at),
        "updated_at": str(negotiation.updated_at),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Start Negotiation
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/negotiations/{negotiation_id}/start")
async def start_negotiation(
    negotiation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Start the negotiation — runs the LangGraph workflow."""
    result = await db.execute(
        select(NegotiationDB)
        .where(NegotiationDB.id == negotiation_id)
        .options(selectinload(NegotiationDB.parties))
    )
    negotiation = result.scalar_one_or_none()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    if negotiation.status not in (
        NegotiationStatus.PENDING.value,
        NegotiationStatus.RESUMED.value,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start negotiation in status '{negotiation.status}'",
        )

    parties = {p.role: p for p in negotiation.parties}
    config = negotiation.config
    settings = get_settings()

    # Prepare initial state
    initial_state = {
        "negotiation_id": negotiation.id,
        "scenario": negotiation.scenario,
        "max_rounds": config.get("max_rounds", settings.max_rounds),
        "party_a_name": parties.get("party_a", PartyDB(name="Party A")).name,
        "party_b_name": parties.get("party_b", PartyDB(name="Party B")).name,
        "party_a_preferences": parties["party_a"].preferences if "party_a" in parties else {},
        "party_b_preferences": parties["party_b"].preferences if "party_b" in parties else {},
        "current_round": 0,
        "active_party": "party_a",
        "status": NegotiationStatus.PENDING.value,
        "offers_history": [],
        "events": [],
        "cost_metrics": [],
        "validation_retries": 0,
    }

    # Update status
    negotiation.status = NegotiationStatus.IN_PROGRESS.value
    await db.flush()
    await db.commit()

    # Run negotiation in background task
    event_service = get_event_service()

    async def _run():
        try:
            from app.graph.negotiation_graph import get_compiled_graph
            graph = get_compiled_graph()

            from app.database import async_session_factory
            from app.models.database_models import OfferDB, NegotiationEventDB, CostTrackingDB, AgreementDB
            from app.models.schemas import StructuredOffer, NegotiationStatus
            import json
            
            saved_offers = 0
            saved_events = 0
            saved_costs = 0
            
            async for current_state in graph.astream(initial_state, stream_mode="values", config={"recursion_limit": 150}):
                async with async_session_factory() as session:
                    neg = await session.get(NegotiationDB, negotiation_id)
                    if not neg:
                        break
                        
                    # 1. Store NEW offers
                    offers = current_state.get("offers_history", [])
                    while saved_offers < len(offers):
                        offer_dict = offers[saved_offers]
                        offer = StructuredOffer(**offer_dict)
                        offer_db = OfferDB(
                            negotiation_id=negotiation_id,
                            round_number=offer.round,
                            party_role=offer.party.value,
                            terms_json=json.dumps(offer.terms, default=str),
                            reasoning=offer.reasoning_summary,
                            concessions_json=json.dumps(offer.concessions),
                            requested_concessions_json=json.dumps(offer.requested_concessions),
                            validation_result="valid",
                        )
                        session.add(offer_db)
                        saved_offers += 1
                        
                    # 2. Store NEW events & Publish via SSE
                    events = current_state.get("events", [])
                    while saved_events < len(events):
                        evt = events[saved_events]
                        evt_db = NegotiationEventDB(
                            negotiation_id=negotiation_id,
                            event_type=evt.get("event_type", ""),
                            round_number=evt.get("round", 0),
                            data_json=json.dumps(evt.get("data", {}), default=str),
                        )
                        session.add(evt_db)
                        await event_service.publish(negotiation_id, evt)
                        saved_events += 1
                        
                    # 3. Store NEW cost metrics
                    costs = current_state.get("cost_metrics", [])
                    while saved_costs < len(costs):
                        cost = costs[saved_costs]
                        cost_db = CostTrackingDB(
                            negotiation_id=negotiation_id,
                            round_number=cost.get("round", 0),
                            input_tokens=cost.get("input_tokens", 0),
                            output_tokens=cost.get("output_tokens", 0),
                            estimated_cost=cost.get("estimated_cost", 0.0),
                            latency_ms=cost.get("latency_ms", 0.0),
                            model=cost.get("model", ""),
                        )
                        session.add(cost_db)
                        saved_costs += 1
                        
                    # 4. Store agreement if present
                    agreement = current_state.get("agreement")
                    if agreement and neg.status != "awaiting_approval":
                        agreement_db = AgreementDB(
                            negotiation_id=negotiation_id,
                            final_terms_json=json.dumps(agreement.get("final_terms", {}), default=str),
                            party_a_satisfaction=agreement.get("party_a_satisfaction", 0),
                            party_b_satisfaction=agreement.get("party_b_satisfaction", 0),
                            fairness_score=agreement.get("fairness_score", 0),
                            constraint_violations=agreement.get("constraint_violations", 0),
                            total_rounds=agreement.get("total_rounds", 0),
                        )
                        session.add(agreement_db)
                        
                    # 5. Update status
                    neg.status = current_state.get("status", NegotiationStatus.FAILED.value)
                    neg.current_round = current_state.get("current_round", 0)
                    
                    await session.commit()
            
            await event_service.close_negotiation(negotiation_id)
            logger.info("negotiation_persisted", id=negotiation_id, status=neg.status, rounds=neg.current_round)

        except Exception as e:
            logger.error("negotiation_run_failed", id=negotiation_id, error=str(e))
            try:
                from app.database import async_session_factory
                async with async_session_factory() as session:
                    neg = await session.get(NegotiationDB, negotiation_id)
                    if neg:
                        neg.status = NegotiationStatus.FAILED.value
                        await session.commit()
                    await event_service.publish(negotiation_id, {
                        "event_type": "NEGOTIATION_FAILED",
                        "data": {"error": str(e)},
                    })
                    await event_service.close_negotiation(negotiation_id)
            except Exception:
                pass

    asyncio.create_task(_run())

    return {
        "id": negotiation_id,
        "status": "in_progress",
        "message": "Negotiation started. Subscribe to /api/negotiations/{id}/events for live updates.",
    }


# ═══════════════════════════════════════════════════════════════════════════
# SSE Events Stream
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/negotiations/{negotiation_id}/events")
async def stream_events(negotiation_id: str):
    """SSE endpoint for live negotiation updates."""
    event_service = get_event_service()
    queue = event_service.subscribe(negotiation_id)

    return StreamingResponse(
        event_service.event_generator(negotiation_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# Human Approval
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/negotiations/{negotiation_id}/approve")
async def approve_negotiation(
    negotiation_id: str,
    request: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human approves the agreement for their party."""
    result = await db.execute(
        select(NegotiationDB)
        .where(NegotiationDB.id == negotiation_id)
        .options(selectinload(NegotiationDB.agreement))
    )
    negotiation = result.scalar_one_or_none()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    if negotiation.status != NegotiationStatus.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Negotiation is not awaiting approval (status: {negotiation.status})",
        )

    agreement = negotiation.agreement
    if not agreement:
        raise HTTPException(status_code=400, detail="No agreement found")

    # Set approval
    if request.party == PartyRole.PARTY_A:
        agreement.party_a_approved = request.approved
    else:
        agreement.party_b_approved = request.approved

    if not request.approved:
        agreement.rejection_reason = request.reason

    # Check if both parties have responded
    a_done = agreement.party_a_approved is not None
    b_done = agreement.party_b_approved is not None

    event_service = get_event_service()

    if a_done and b_done:
        if agreement.party_a_approved and agreement.party_b_approved:
            negotiation.status = NegotiationStatus.APPROVED.value
            event_type = "HUMAN_APPROVED"
            message = "Both parties approved. Agreement finalized!"
        else:
            negotiation.status = NegotiationStatus.REJECTED.value
            event_type = "HUMAN_REJECTED"
            message = f"Agreement rejected. Reason: {agreement.rejection_reason}"
    else:
        event_type = "APPROVAL_PENDING"
        party_label = "Party A" if request.party == PartyRole.PARTY_A else "Party B"
        action = "approved" if request.approved else "rejected"
        message = f"{party_label} {action}. Waiting for the other party."

    # Store event
    evt_db = NegotiationEventDB(
        negotiation_id=negotiation_id,
        event_type=event_type,
        data_json=json.dumps({
            "party": request.party.value,
            "approved": request.approved,
            "reason": request.reason,
            "message": message,
        }),
    )
    db.add(evt_db)

    await event_service.publish(negotiation_id, {
        "event_type": event_type,
        "data": {
            "party": request.party.value,
            "approved": request.approved,
            "reason": request.reason,
            "message": message,
        },
    })

    return {"status": negotiation.status, "message": message}


@router.post("/negotiations/{negotiation_id}/reject")
async def reject_negotiation(
    negotiation_id: str,
    request: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Human rejects the agreement."""
    request.approved = False
    return await approve_negotiation(negotiation_id, request, db)


@router.post("/negotiations/{negotiation_id}/resume")
async def resume_negotiation(
    negotiation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Resume a rejected negotiation."""
    result = await db.execute(
        select(NegotiationDB)
        .where(NegotiationDB.id == negotiation_id)
        .options(
            selectinload(NegotiationDB.parties),
            selectinload(NegotiationDB.agreement),
        )
    )
    negotiation = result.scalar_one_or_none()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    if negotiation.status != NegotiationStatus.REJECTED.value:
        raise HTTPException(
            status_code=400,
            detail="Can only resume a rejected negotiation",
        )

    # Delete old agreement
    if negotiation.agreement:
        await db.delete(negotiation.agreement)

    # Reset status
    negotiation.status = NegotiationStatus.RESUMED.value

    event_service = get_event_service()
    await event_service.publish(negotiation_id, {
        "event_type": "NEGOTIATION_RESUMED",
        "data": {"message": "Negotiation resumed after rejection."},
    })

    evt_db = NegotiationEventDB(
        negotiation_id=negotiation_id,
        event_type="NEGOTIATION_RESUMED",
        data_json=json.dumps({"message": "Negotiation resumed after rejection."}),
    )
    db.add(evt_db)

    return {"id": negotiation_id, "status": "resumed", "message": "Negotiation resumed. Call /start to begin new rounds."}


@router.get("/negotiations/{negotiation_id}/agreement")
async def get_agreement(
    negotiation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the final agreement details."""
    result = await db.execute(
        select(NegotiationDB)
        .where(NegotiationDB.id == negotiation_id)
        .options(selectinload(NegotiationDB.agreement))
    )
    negotiation = result.scalar_one_or_none()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    if not negotiation.agreement:
        raise HTTPException(status_code=404, detail="No agreement reached yet")

    a = negotiation.agreement
    return {
        "final_terms": a.final_terms,
        "party_a_satisfaction": a.party_a_satisfaction,
        "party_b_satisfaction": a.party_b_satisfaction,
        "fairness_score": a.fairness_score,
        "constraint_violations": a.constraint_violations,
        "total_rounds": a.total_rounds,
        "party_a_approved": a.party_a_approved,
        "party_b_approved": a.party_b_approved,
        "rejection_reason": a.rejection_reason,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Party-Specific Dashboard
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/negotiations/{negotiation_id}/dashboard/{party}")
async def get_party_dashboard(
    negotiation_id: str,
    party: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get party-specific dashboard data.

    Returns ONLY that party's private preferences plus the shared
    negotiation timeline. The other party's preferences are NEVER exposed.
    """
    if party not in ("tenant", "host", "party_a", "party_b"):
        raise HTTPException(status_code=400, detail="Party must be 'tenant' or 'host'")

    # Normalize: tenant = party_a, host = party_b
    party_role = "party_a" if party in ("tenant", "party_a") else "party_b"
    other_role = "party_b" if party_role == "party_a" else "party_a"

    result = await db.execute(
        select(NegotiationDB)
        .where(NegotiationDB.id == negotiation_id)
        .options(
            selectinload(NegotiationDB.parties),
            selectinload(NegotiationDB.offers),
            selectinload(NegotiationDB.events),
            selectinload(NegotiationDB.agreement),
            selectinload(NegotiationDB.cost_records),
        )
    )
    negotiation = result.scalar_one_or_none()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    config = negotiation.config
    parties = {p.role: p for p in negotiation.parties}

    # MY preferences (private — only I see these)
    my_party = parties.get(party_role)
    my_preferences = my_party.preferences if my_party else {}

    # Build offers — show terms to everyone, but reasoning only for MY agent
    offers = []
    for o in negotiation.offers:
        is_mine = o.party_role == party_role
        offers.append({
            "round": o.round_number,
            "party": o.party_role,
            "party_label": "You" if is_mine else ("Host" if party_role == "party_a" else "Tenant"),
            "is_mine": is_mine,
            "terms": o.terms,
            "reasoning": o.reasoning if is_mine else None,  # Hide other's reasoning
            "concessions": o.concessions if is_mine else None,
            "created_at": str(o.created_at),
        })

    # Build events
    events = []
    for e in negotiation.events:
        evt_data = dict(e.data or {})
        # Filter reasoning from events too
        if evt_data.get("party") == other_role and "reasoning" in evt_data:
            evt_data["reasoning"] = None
        events.append({
            "event_type": e.event_type,
            "round": e.round_number,
            "data": evt_data,
            "timestamp": str(e.timestamp),
        })

    # Agreement data
    agreement_data = None
    if negotiation.agreement:
        a = negotiation.agreement
        my_satisfaction = a.party_a_satisfaction if party_role == "party_a" else a.party_b_satisfaction
        my_approved = a.party_a_approved if party_role == "party_a" else a.party_b_approved
        other_approved = a.party_b_approved if party_role == "party_a" else a.party_a_approved

        agreement_data = {
            "final_terms": a.final_terms,
            "my_satisfaction": my_satisfaction,
            "other_satisfaction": a.party_b_satisfaction if party_role == "party_a" else a.party_a_satisfaction,
            "fairness_score": a.fairness_score,
            "constraint_violations": a.constraint_violations,
            "total_rounds": a.total_rounds,
            "my_approved": my_approved,
            "other_approved": other_approved,
            "rejection_reason": a.rejection_reason,
        }

    # Cost summary
    total_cost = sum(c.estimated_cost for c in negotiation.cost_records)
    total_calls = len(negotiation.cost_records)

    return {
        "id": negotiation.id,
        "status": negotiation.status,
        "party_role": party_role,
        "party_label": "Tenant" if party_role == "party_a" else "Host",
        "other_label": "Host" if party_role == "party_a" else "Tenant",
        "my_name": my_party.name if my_party else party_role,
        "my_preferences": my_preferences,
        "current_round": negotiation.current_round,
        "max_rounds": config.get("max_rounds", 10),
        "offers": offers,
        "events": events,
        "agreement": agreement_data,
        "cost_summary": {
            "total_estimated_cost": round(total_cost, 6),
            "total_llm_calls": total_calls,
        },
        "created_at": str(negotiation.created_at),
    }

