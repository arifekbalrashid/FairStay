import re

with open("app/api/negotiations.py", "r") as f:
    content = f.read()

# Replace the run block in start_property_negotiation (around line 174)
old_run = """    async def _run():
        try:
            from app.graph.negotiation_graph import run_negotiation
            final_state = await run_negotiation(initial_state)

            # Persist results to database
            from app.database import async_session_factory
            async with async_session_factory() as session:
                neg = await session.get(NegotiationDB, neg_id)
                if not neg:
                    return

                # Store offers
                from app.models.database_models import OfferDB, NegotiationEventDB, CostTrackingDB, AgreementDB
                from app.models.schemas import StructuredOffer, NegotiationStatus
                import json

                for offer_dict in final_state.get("offers_history", []):
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

                # Store events
                for evt in final_state.get("events", []):
                    evt_db = NegotiationEventDB(
                        negotiation_id=neg_id,
                        event_type=evt.get("event_type", ""),
                        round_number=evt.get("round", 0),
                        data_json=json.dumps(evt.get("data", {}), default=str),
                    )
                    session.add(evt_db)

                # Store cost metrics
                for cost in final_state.get("cost_metrics", []):
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

                # Store agreement
                agreement = final_state.get("agreement")
                if agreement:
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

                # Update negotiation status
                neg.status = final_state.get("status", "failed")
                neg.current_round = final_state.get("current_round", 0)

                await session.commit()

                # Publish events to SSE subscribers
                for evt in final_state.get("events", []):
                    await event_service.publish(neg_id, evt)

                await event_service.close_negotiation(neg_id)

        except Exception as e:"""

new_run = """    async def _run():
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
                        
                    # 4. Store agreement if present (only at the end)
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

        except Exception as e:"""

if old_run in content:
    content = content.replace(old_run, new_run)
    print("Replaced start_property_negotiation _run")
else:
    print("Could not find old_run block 1")

# Replace in start_negotiation
old_run_2 = """    async def _run():
        try:
            final_state = await run_negotiation(initial_state)

            # Persist results to database
            from app.database import async_session_factory
            async with async_session_factory() as session:
                # Reload negotiation
                neg = await session.get(NegotiationDB, negotiation_id)
                if not neg:
                    return

                # Store offers
                for offer_dict in final_state.get("offers_history", []):
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

                # Store events
                for evt in final_state.get("events", []):
                    evt_db = NegotiationEventDB(
                        negotiation_id=negotiation_id,
                        event_type=evt.get("event_type", ""),
                        round_number=evt.get("round", 0),
                        data_json=json.dumps(evt.get("data", {}), default=str),
                    )
                    session.add(evt_db)

                # Store cost metrics
                for cost in final_state.get("cost_metrics", []):
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

                # Store agreement
                agreement = final_state.get("agreement")
                if agreement:
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

                # Update negotiation status
                neg.status = final_state.get("status", NegotiationStatus.FAILED.value)
                neg.current_round = final_state.get("current_round", 0)

                await session.commit()

                # Publish events to SSE subscribers
                for evt in final_state.get("events", []):
                    await event_service.publish(negotiation_id, evt)

                await event_service.close_negotiation(negotiation_id)

                logger.info(
                    "negotiation_persisted",
                    id=negotiation_id,
                    status=neg.status,
                    rounds=neg.current_round,
                )

        except Exception as e:"""

new_run_2 = """    async def _run():
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

        except Exception as e:"""

if old_run_2 in content:
    content = content.replace(old_run_2, new_run_2)
    print("Replaced start_negotiation _run")
else:
    print("Could not find old_run_2 block")

with open("app/api/negotiations.py", "w") as f:
    f.write(content)
