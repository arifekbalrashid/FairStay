"""LangGraph negotiation workflow — builds and compiles the state machine."""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    advance_round,
    check_evaluation,
    check_rounds,
    check_validation,
    evaluate_offer,
    finalize_agreement,
    generate_offer,
    handle_failure,
    increment_retry,
    initialize_negotiation,
    record_offer,
    validate_offer,
)
from app.graph.state import NegotiationState

logger = structlog.get_logger()


def build_negotiation_graph() -> StateGraph:
    """
    Build the negotiation state machine.

    Flow:
        START → initialize → generate_offer → validate_offer
            → (valid) → record_offer → evaluate_offer
                → (accepted) → finalize_agreement → END
                → (rejected) → check_rounds
                    → (continue) → advance_round → generate_offer
                    → (max_rounds) → handle_failure → END
            → (retry) → increment_retry → generate_offer
            → (failed) → handle_failure → END
    """
    graph = StateGraph(NegotiationState)

    # Add nodes
    graph.add_node("initialize", initialize_negotiation)
    graph.add_node("generate_offer", generate_offer)
    graph.add_node("validate_offer", validate_offer)
    graph.add_node("increment_retry", increment_retry)
    graph.add_node("record_offer", record_offer)
    graph.add_node("evaluate_offer", evaluate_offer)
    graph.add_node("finalize_agreement", finalize_agreement)
    graph.add_node("handle_failure", handle_failure)
    graph.add_node("advance_round", advance_round)

    # Edges
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "generate_offer")

    # After generating offer → validate
    graph.add_edge("generate_offer", "validate_offer")

    # After validation → conditional routing
    graph.add_conditional_edges(
        "validate_offer",
        check_validation,
        {
            "valid": "record_offer",
            "retry": "increment_retry",
            "failed": "handle_failure",
        },
    )

    # Retry → generate again
    graph.add_edge("increment_retry", "generate_offer")

    # After recording → evaluate
    graph.add_edge("record_offer", "evaluate_offer")

    # After evaluation → conditional routing
    graph.add_conditional_edges(
        "evaluate_offer",
        check_evaluation,
        {
            "accepted": "finalize_agreement",
            "rejected": "advance_round",
            "failed": "handle_failure",
        },
    )

    # After advancing round → check max rounds
    graph.add_conditional_edges(
        "advance_round",
        check_rounds,
        {
            "continue": "generate_offer",
            "max_rounds": "handle_failure",
        },
    )

    # Terminal nodes
    graph.add_edge("finalize_agreement", END)
    graph.add_edge("handle_failure", END)

    return graph


# ─── Compiled graph (reusable) ──────────────────────────────────────────────

_compiled_graph = None


def get_compiled_graph():
    """Return the compiled negotiation graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_negotiation_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph


async def run_negotiation(initial_state: dict[str, Any]) -> dict[str, Any]:
    """
    Execute the complete negotiation workflow.

    Args:
        initial_state: Dict containing negotiation_id, scenario, preferences, etc.

    Returns:
        Final state after negotiation completes.
    """
    graph = get_compiled_graph()

    logger.info("negotiation_workflow_started", negotiation_id=initial_state.get("negotiation_id"))

    # Run the graph with increased recursion limit
    # Each round uses ~5-6 node transitions, so max_rounds=10 needs ~60+
    final_state = await graph.ainvoke(
        initial_state,
        config={"recursion_limit": 150},
    )

    logger.info(
        "negotiation_workflow_completed",
        negotiation_id=initial_state.get("negotiation_id"),
        status=final_state.get("status"),
        rounds=final_state.get("current_round"),
    )

    return final_state
