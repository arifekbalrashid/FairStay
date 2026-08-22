"""LangGraph state definition for the negotiation workflow."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from typing_extensions import TypedDict

from app.models.schemas import (
    CostMetrics,
    NegotiationEventData,
    NegotiationStatus,
    PartyRole,
    StructuredOffer,
    ValidationResult,
)


def _append_list(existing: list, new: list) -> list:
    """Reducer that appends new items to an existing list."""
    return existing + new


class NegotiationState(TypedDict, total=False):
    """Complete state for the LangGraph negotiation workflow."""

    # ── Identity ──
    negotiation_id: str
    scenario: str
    max_rounds: int
    party_a_name: str
    party_b_name: str

    # ── Private preferences (NEVER sent to opposing agent) ──
    party_a_preferences: dict[str, Any]
    party_b_preferences: dict[str, Any]

    # ── Negotiation progress ──
    current_round: int
    active_party: str  # "party_a" or "party_b"
    status: str  # NegotiationStatus value

    # ── Offers ──
    current_offer: Optional[dict[str, Any]]  # Serialized StructuredOffer
    offers_history: Annotated[list[dict[str, Any]], _append_list]

    # ── Validation ──
    last_validation: Optional[dict[str, Any]]  # Serialized ValidationResult
    validation_retries: int

    # ── Evaluation ──
    offer_accepted: Optional[bool]
    evaluation_reasoning: str

    # ── Agreement ──
    agreement: Optional[dict[str, Any]]

    # ── Events (append-only) ──
    events: Annotated[list[dict[str, Any]], _append_list]

    # ── Cost tracking (append-only) ──
    cost_metrics: Annotated[list[dict[str, Any]], _append_list]

    # ── Error handling ──
    error: Optional[str]
    failure_reason: Optional[str]
