"""LangGraph node functions for the negotiation state machine."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from app.agents.base_agent import NegotiationAgent
from app.agents.party_a_agent import PartyAAgent
from app.agents.party_b_agent import PartyBAgent
from app.graph.state import NegotiationState
from app.models.schemas import (
    EventType,
    NegotiationStatus,
    PartyPreferences,
    PartyRole,
    StructuredOffer,
    ValidationResult,
)
from app.negotiation.engine import get_variable_names
from app.negotiation.scorer import NegotiationScorer
from app.negotiation.validator import AgreementValidator, ConstraintValidator, OfferValidator

logger = structlog.get_logger()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_event(event_type: EventType, round_num: int = 0, data: dict | None = None) -> dict:
    return {
        "event_type": event_type.value,
        "round": round_num,
        "data": data or {},
        "timestamp": _now_iso(),
    }


def _get_agent(state: NegotiationState, role: str) -> NegotiationAgent:
    """Create an agent for the given role from state. Only gives it its OWN preferences."""
    if role == "party_a":
        prefs = PartyPreferences(**state["party_a_preferences"])
        return PartyAAgent(
            name=state.get("party_a_name", "Party A"),
            preferences=prefs,
            scenario=state["scenario"],
        )
    else:
        prefs = PartyPreferences(**state["party_b_preferences"])
        return PartyBAgent(
            name=state.get("party_b_name", "Party B"),
            preferences=prefs,
            scenario=state["scenario"],
        )


def _deserialize_offers(history: list[dict]) -> list[StructuredOffer]:
    """Convert serialized offer dicts back to StructuredOffer objects."""
    return [StructuredOffer(**o) for o in history]


# ═══════════════════════════════════════════════════════════════════════════
# Node: Initialize Negotiation
# ═══════════════════════════════════════════════════════════════════════════

def initialize_negotiation(state: NegotiationState) -> dict:
    """Set up the initial negotiation state."""
    logger.info("node_initialize", negotiation_id=state.get("negotiation_id"))
    return {
        "current_round": 1,
        "active_party": "party_a",
        "status": NegotiationStatus.IN_PROGRESS.value,
        "validation_retries": 0,
        "offer_accepted": None,
        "events": [_make_event(EventType.NEGOTIATION_STARTED, data={
            "scenario": state["scenario"],
            "max_rounds": state["max_rounds"],
            "party_a": state.get("party_a_name", "Party A"),
            "party_b": state.get("party_b_name", "Party B"),
        })],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Generate Offer
# ═══════════════════════════════════════════════════════════════════════════

async def generate_offer(state: NegotiationState) -> dict:
    """Active agent generates an offer or counteroffer."""
    active = state["active_party"]
    round_num = state["current_round"]
    agent = _get_agent(state, active)
    history = _deserialize_offers(state.get("offers_history", []))

    # Determine if this is a counteroffer
    is_counter = len(history) > 0
    incoming = None
    if is_counter and history:
        incoming = history[-1]  # Last offer from the other party

    logger.info("node_generate_offer", party=active, round=round_num, is_counter=is_counter)

    try:
        offer, metrics = await agent.generate_offer(
            round_number=round_num,
            max_rounds=state["max_rounds"],
            offer_history=history,
            incoming_offer=incoming,
            is_counter=is_counter,
        )

        event_type = EventType.COUNTEROFFER_GENERATED if is_counter else EventType.OFFER_GENERATED

        return {
            "current_offer": offer.model_dump(),
            "validation_retries": 0,
            "events": [_make_event(event_type, round_num, {
                "party": active,
                "party_name": agent.name,
                "terms": offer.terms,
                "reasoning": offer.reasoning_summary,
                "concessions": offer.concessions,
                "requested_concessions": offer.requested_concessions,
            })],
            "cost_metrics": [metrics.model_dump()],
        }

    except Exception as e:
        logger.error("generate_offer_failed", error=str(e), party=active)
        return {
            "error": str(e),
            "status": NegotiationStatus.FAILED.value,
            "failure_reason": f"Failed to generate offer: {str(e)}",
            "events": [_make_event(EventType.MODEL_ERROR, round_num, {
                "party": active,
                "error": str(e),
            })],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Validate Offer
# ═══════════════════════════════════════════════════════════════════════════

def validate_offer(state: NegotiationState) -> dict:
    """Deterministically validate the current offer against constraints."""
    offer_dict = state.get("current_offer")
    if not offer_dict:
        return {
            "last_validation": {"valid": False, "violations": ["No offer to validate"], "warnings": []},
            "events": [_make_event(EventType.VALIDATION_FAILED, state.get("current_round", 0), {
                "error": "No offer generated",
            })],
        }

    offer = StructuredOffer(**offer_dict)
    active = state["active_party"]
    scenario = state["scenario"]

    # Get the OFFERING party's own preferences for constraint checking
    if active == "party_a":
        prefs = PartyPreferences(**state["party_a_preferences"])
    else:
        prefs = PartyPreferences(**state["party_b_preferences"])

    # Validate structure
    variable_names = get_variable_names(scenario)
    struct_result = OfferValidator.validate_structure(offer, variable_names)

    # Validate constraints
    constraint_result = ConstraintValidator.validate(offer, prefs)

    # Merge results
    all_violations = struct_result.violations + constraint_result.violations
    all_warnings = struct_result.warnings + constraint_result.warnings
    is_valid = len(all_violations) == 0

    result = ValidationResult(valid=is_valid, violations=all_violations, warnings=all_warnings)

    logger.info("node_validate_offer", valid=is_valid, violations=all_violations, party=active)

    event_type = EventType.OFFER_VALIDATED if is_valid else EventType.VALIDATION_FAILED
    return {
        "last_validation": result.model_dump(),
        "events": [_make_event(event_type, state.get("current_round", 0), {
            "valid": is_valid,
            "violations": all_violations,
            "warnings": all_warnings,
            "party": active,
        })],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Record Offer
# ═══════════════════════════════════════════════════════════════════════════

def record_offer(state: NegotiationState) -> dict:
    """Record a validated offer in history."""
    offer_dict = state.get("current_offer")
    if not offer_dict:
        return {}
    return {
        "offers_history": [offer_dict],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Evaluate Offer
# ═══════════════════════════════════════════════════════════════════════════

async def evaluate_offer(state: NegotiationState) -> dict:
    """The OPPOSING agent evaluates the current offer."""
    active = state["active_party"]
    opposing = "party_b" if active == "party_a" else "party_a"
    round_num = state["current_round"]

    offer = StructuredOffer(**state["current_offer"])
    history = _deserialize_offers(state.get("offers_history", []))

    # The OPPOSING agent evaluates — gets only ITS OWN preferences
    agent = _get_agent(state, opposing)

    logger.info("node_evaluate_offer", evaluator=opposing, round=round_num)

    try:
        accept, reasoning, metrics = await agent.evaluate_offer(
            offer=offer,
            round_number=round_num,
            max_rounds=state["max_rounds"],
            offer_history=history,
        )

        # Also validate against the EVALUATING party's hard constraints
        if opposing == "party_a":
            eval_prefs = PartyPreferences(**state["party_a_preferences"])
        else:
            eval_prefs = PartyPreferences(**state["party_b_preferences"])

        constraint_check = ConstraintValidator.validate(offer, eval_prefs)
        if not constraint_check.valid:
            accept = False
            reasoning = f"Offer violates constraints: {', '.join(constraint_check.violations)}"

        return {
            "offer_accepted": accept,
            "evaluation_reasoning": reasoning,
            "events": [_make_event(
                EventType.AGREEMENT_REACHED if accept else EventType.OFFER_REJECTED,
                round_num,
                {
                    "evaluator": opposing,
                    "evaluator_name": agent.name,
                    "accepted": accept,
                    "reasoning": reasoning,
                },
            )],
            "cost_metrics": [metrics.model_dump()],
        }

    except Exception as e:
        logger.error("evaluate_offer_failed", error=str(e), evaluator=opposing)
        return {
            "offer_accepted": False,
            "evaluation_reasoning": f"Evaluation failed: {str(e)}",
            "events": [_make_event(EventType.MODEL_ERROR, round_num, {
                "evaluator": opposing,
                "error": str(e),
            })],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Finalize Agreement
# ═══════════════════════════════════════════════════════════════════════════

def finalize_agreement(state: NegotiationState) -> dict:
    """Calculate scores and create agreement record."""
    offer = StructuredOffer(**state["current_offer"])
    party_a_prefs = PartyPreferences(**state["party_a_preferences"])
    party_b_prefs = PartyPreferences(**state["party_b_preferences"])
    history = _deserialize_offers(state.get("offers_history", []))

    result = NegotiationScorer.score_agreement(
        final_terms=offer.terms,
        party_a_prefs=party_a_prefs,
        party_b_prefs=party_b_prefs,
        total_rounds=state["current_round"],
        offers=history,
    )

    logger.info(
        "agreement_finalized",
        party_a_satisfaction=result.party_a_satisfaction,
        party_b_satisfaction=result.party_b_satisfaction,
        fairness=result.fairness_score,
    )

    return {
        "status": NegotiationStatus.AWAITING_APPROVAL.value,
        "agreement": result.model_dump(),
        "events": [_make_event(EventType.AGREEMENT_REACHED, state["current_round"], {
            "final_terms": result.final_terms,
            "party_a_satisfaction": result.party_a_satisfaction,
            "party_b_satisfaction": result.party_b_satisfaction,
            "fairness_score": result.fairness_score,
            "total_rounds": result.total_rounds,
        })],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Handle Failure
# ═══════════════════════════════════════════════════════════════════════════

def handle_failure(state: NegotiationState) -> dict:
    """Handle negotiation failure."""
    reason = state.get("failure_reason", "Unknown failure")
    if state.get("current_round", 0) >= state.get("max_rounds", 10):
        reason = f"No agreement reached within {state['max_rounds']} rounds."

    logger.warning("negotiation_failed", reason=reason)

    return {
        "status": NegotiationStatus.FAILED.value,
        "failure_reason": reason,
        "events": [_make_event(EventType.NEGOTIATION_FAILED, state.get("current_round", 0), {
            "reason": reason,
        })],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Advance Round
# ═══════════════════════════════════════════════════════════════════════════

def advance_round(state: NegotiationState) -> dict:
    """Switch to the opposing party and advance the round."""
    active = state["active_party"]
    new_active = "party_b" if active == "party_a" else "party_a"
    new_round = state["current_round"] + 1

    return {
        "active_party": new_active,
        "current_round": new_round,
        "offer_accepted": None,
        "validation_retries": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Conditional Edge Functions
# ═══════════════════════════════════════════════════════════════════════════

def check_validation(state: NegotiationState) -> str:
    """Route based on offer validation result."""
    validation = state.get("last_validation", {})
    if validation.get("valid", False):
        return "valid"

    retries = state.get("validation_retries", 0)
    max_retries = 3
    if retries < max_retries:
        return "retry"
    return "failed"


def check_evaluation(state: NegotiationState) -> str:
    """Route based on offer evaluation."""
    if state.get("status") == NegotiationStatus.FAILED.value:
        return "failed"
    if state.get("offer_accepted", False):
        return "accepted"
    return "rejected"


def check_rounds(state: NegotiationState) -> str:
    """Check if max rounds exceeded."""
    current = state.get("current_round", 0)
    max_rounds = state.get("max_rounds", 10)
    if current >= max_rounds:
        return "max_rounds"
    return "continue"


def increment_retry(state: NegotiationState) -> dict:
    """Increment the validation retry counter."""
    return {
        "validation_retries": state.get("validation_retries", 0) + 1,
    }
