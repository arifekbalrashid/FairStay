"""Pydantic schemas used across the application."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Enums ──────────────────────────────────────────────────────────────────

class NegotiationScenario(str, enum.Enum):
    RENTAL = "rental"


class NegotiationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AGREEMENT_REACHED = "agreement_reached"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    RESUMED = "resumed"


class PartyRole(str, enum.Enum):
    PARTY_A = "party_a"
    PARTY_B = "party_b"


class EventType(str, enum.Enum):
    NEGOTIATION_STARTED = "NEGOTIATION_STARTED"
    OFFER_GENERATED = "OFFER_GENERATED"
    OFFER_VALIDATED = "OFFER_VALIDATED"
    OFFER_REJECTED = "OFFER_REJECTED"
    COUNTEROFFER_GENERATED = "COUNTEROFFER_GENERATED"
    AGREEMENT_REACHED = "AGREEMENT_REACHED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    NEGOTIATION_FAILED = "NEGOTIATION_FAILED"
    NEGOTIATION_RESUMED = "NEGOTIATION_RESUMED"
    MODEL_ERROR = "MODEL_ERROR"
    VALIDATION_FAILED = "VALIDATION_FAILED"


class NegotiationStyle(str, enum.Enum):
    AGGRESSIVE = "aggressive"
    MODERATE = "moderate"
    FLEXIBLE = "flexible"
    FIRM = "firm"


# ─── Party Preferences ─────────────────────────────────────────────────────

class PartyPreferences(BaseModel):
    """Private preferences for one negotiation party."""

    hard_constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Absolute limits that must never be violated (e.g., max_rent: 20000).",
    )
    soft_preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Preferences that are desirable but negotiable.",
    )
    ideal_values: dict[str, Any] = Field(
        default_factory=dict,
        description="Best-case values for each negotiation variable.",
    )
    acceptable_values: dict[str, Any] = Field(
        default_factory=dict,
        description="The range of acceptable values (worst the party will agree to).",
    )
    priorities: list[str] = Field(
        default_factory=list,
        description="Ordered list of what matters most to this party.",
    )
    negotiation_style: NegotiationStyle = Field(
        default=NegotiationStyle.MODERATE,
        description="How aggressively the agent should negotiate.",
    )
    private_information: str = Field(
        default="",
        description="Free-form private context that only this party's agent should know.",
    )


# ─── Offer ──────────────────────────────────────────────────────────────────

class StructuredOffer(BaseModel):
    """A single structured negotiation offer."""

    round: int = Field(ge=1, description="Round number (1-indexed).")
    party: PartyRole
    terms: dict[str, Any] = Field(description="Key-value pairs of negotiation variables.")
    reasoning_summary: str = Field(
        default="",
        description="Short, user-safe explanation for this offer.",
    )
    concessions: list[str] = Field(
        default_factory=list,
        description="Concessions made in this offer.",
    )
    requested_concessions: list[str] = Field(
        default_factory=list,
        description="Concessions requested from the other party.",
    )


class OfferEvaluation(BaseModel):
    """The agent's evaluation of a received offer."""

    accept: bool = Field(description="Whether to accept the offer.")
    reasoning: str = Field(description="Short user-safe explanation.")
    acceptable_terms: list[str] = Field(
        default_factory=list,
        description="Terms that are acceptable.",
    )
    unacceptable_terms: list[str] = Field(
        default_factory=list,
        description="Terms that need further negotiation.",
    )
    willingness_to_concede: dict[str, str] = Field(
        default_factory=dict,
        description="For each unacceptable term, how willing to move (low/medium/high).",
    )


class LLMOfferProposal(BaseModel):
    """Schema for LLM-generated offers (used with with_structured_output)."""

    terms: dict[str, Any] = Field(
        description="Proposed negotiation terms as key-value pairs. MUST be a valid JSON object (dictionary), not a string."
    )
    reasoning_summary: str = Field(
        description="Short, user-safe explanation for this proposal."
    )
    concessions: list[str] = Field(
        default_factory=list,
        description="Concessions being made.",
    )
    requested_concessions: list[str] = Field(
        default_factory=list,
        description="Concessions requested from the other party.",
    )


class LLMOfferEvaluation(BaseModel):
    """Schema for LLM-generated evaluations (used with with_structured_output)."""

    accept: str = Field(description="Must be the string 'true' if the offer should be accepted, or 'false' if rejected.")
    reasoning: str = Field(description="Short explanation for the decision.")
    acceptable_terms: list[str] = Field(
        default_factory=list,
        description="Which terms are satisfactory.",
    )
    unacceptable_terms: list[str] = Field(
        default_factory=list,
        description="Which terms need further negotiation.",
    )
    proposed_counter_terms: dict[str, Any] = Field(
        default_factory=dict,
        description="Suggested counter-values for unacceptable terms.",
    )


# ─── Validation ─────────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    """Result of validating an offer against constraints."""

    valid: bool
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ─── Agreement ──────────────────────────────────────────────────────────────

class AgreementResult(BaseModel):
    """Final agreement with satisfaction scores."""

    final_terms: dict[str, Any]
    party_a_satisfaction: float = Field(ge=0, le=100)
    party_b_satisfaction: float = Field(ge=0, le=100)
    fairness_score: float = Field(ge=0, le=100)
    constraint_violations: int = 0
    total_rounds: int
    total_concessions_a: int = 0
    total_concessions_b: int = 0


# ─── Negotiation Config ────────────────────────────────────────────────────

class NegotiationConfig(BaseModel):
    """Configuration for a negotiation session."""

    scenario: NegotiationScenario
    max_rounds: int = Field(default=10, ge=1, le=50)
    party_a_name: str = Field(default="Party A")
    party_b_name: str = Field(default="Party B")


# ─── API Request / Response ────────────────────────────────────────────────

class CreateNegotiationRequest(BaseModel):
    """Request to create a new negotiation."""

    config: NegotiationConfig
    party_a_preferences: PartyPreferences
    party_b_preferences: PartyPreferences


class NegotiationSummary(BaseModel):
    """Summary of a negotiation for list views."""

    id: str
    scenario: NegotiationScenario
    status: NegotiationStatus
    party_a_name: str
    party_b_name: str
    current_round: int = 0
    max_rounds: int = 10
    created_at: datetime
    updated_at: Optional[datetime] = None


class NegotiationDetail(BaseModel):
    """Full negotiation details including history."""

    id: str
    scenario: NegotiationScenario
    status: NegotiationStatus
    config: NegotiationConfig
    party_a_name: str
    party_b_name: str
    current_round: int = 0
    offers: list[StructuredOffer] = Field(default_factory=list)
    agreement: Optional[AgreementResult] = None
    events: list[NegotiationEventData] = Field(default_factory=list)
    cost_summary: Optional[CostSummary] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ApprovalRequest(BaseModel):
    """Human approval or rejection."""

    party: PartyRole
    approved: bool
    reason: str = ""


# ─── Properties ─────────────────────────────────────────────────────────────

class PropertyBase(BaseModel):
    title: str
    description: str
    location: str
    property_type: str = "apartment"
    bedrooms: int = 1
    beds: int = 1
    bathrooms: float = 1.0
    amenities: list[str] = Field(default_factory=list)
    base_price: float
    currency: str = "INR"
    cleaning_fee: float = 0.0
    deposit: float = 0.0
    minimum_stay: int = 1
    maximum_stay: int = 30
    images: list[str] = Field(default_factory=list)

class PropertyCreate(PropertyBase):
    host_id: str
    negotiation_config: dict[str, Any] = Field(default_factory=dict)

class PropertyResponse(PropertyBase):
    id: str
    host_id: str
    rating: float
    review_count: int
    created_at: datetime
    updated_at: datetime

class PropertySearchRequest(BaseModel):
    location: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    guests: Optional[int] = None
    property_type: Optional[str] = None


# ─── Bookings ───────────────────────────────────────────────────────────────

class BookingResponse(BaseModel):
    id: str
    property_id: str
    negotiation_id: str
    guest_id: Optional[str] = None
    status: str
    final_terms: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ─── Events ─────────────────────────────────────────────────────────────────

class NegotiationEventData(BaseModel):
    """A negotiation event for the event stream."""

    event_type: EventType
    round: int = 0
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Cost Tracking ─────────────────────────────────────────────────────────

class CostMetrics(BaseModel):
    """Cost metrics for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: float = 0.0
    model: str = ""


class CostSummary(BaseModel):
    """Aggregated cost for a negotiation."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_estimated_cost: float = 0.0
    total_llm_calls: int = 0
    average_latency_ms: float = 0.0
    models_used: list[str] = Field(default_factory=list)


# ─── Scenario Metadata ─────────────────────────────────────────────────────

class VariableMetadata(BaseModel):
    """Metadata about a single negotiation variable."""

    name: str
    display_name: str
    type: str  # "number", "boolean", "string", "date"
    unit: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""


class ScenarioMetadata(BaseModel):
    """Metadata about a negotiation scenario."""

    name: NegotiationScenario
    display_name: str
    description: str
    party_a_label: str
    party_b_label: str
    variables: list[VariableMetadata]
    default_party_a: Optional[PartyPreferences] = None
    default_party_b: Optional[PartyPreferences] = None


# ─── Fix forward references ────────────────────────────────────────────────
# NegotiationDetail references NegotiationEventData and CostSummary which
# are defined after it, so we need to rebuild the model.
NegotiationDetail.model_rebuild()
