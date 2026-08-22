"""Tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError
from app.models.schemas import (
    CreateNegotiationRequest,
    NegotiationConfig,
    NegotiationScenario,
    NegotiationStyle,
    PartyPreferences,
    PartyRole,
    StructuredOffer,
    ValidationResult,
    LLMOfferProposal,
    LLMOfferEvaluation,
    AgreementResult,
    CostMetrics,
)


class TestPartyPreferences:
    def test_default_values(self):
        prefs = PartyPreferences()
        assert prefs.hard_constraints == {}
        assert prefs.negotiation_style == NegotiationStyle.MODERATE
        assert prefs.priorities == []

    def test_full_preferences(self):
        prefs = PartyPreferences(
            hard_constraints={"max_rent": 20000},
            soft_preferences={"furnished": True},
            ideal_values={"rent": 17000},
            acceptable_values={"rent": 20000},
            priorities=["rent", "furnished"],
            negotiation_style=NegotiationStyle.AGGRESSIVE,
            private_information="Secret info",
        )
        assert prefs.hard_constraints["max_rent"] == 20000
        assert prefs.negotiation_style == NegotiationStyle.AGGRESSIVE


class TestStructuredOffer:
    def test_valid_offer(self):
        offer = StructuredOffer(
            round=1,
            party=PartyRole.PARTY_A,
            terms={"rent": 19000, "parking": True},
            reasoning_summary="Fair opening offer.",
            concessions=[],
            requested_concessions=["parking"],
        )
        assert offer.round == 1
        assert offer.terms["rent"] == 19000

    def test_round_must_be_positive(self):
        with pytest.raises(ValidationError):
            StructuredOffer(round=0, party=PartyRole.PARTY_A, terms={})


class TestNegotiationConfig:
    def test_default_max_rounds(self):
        config = NegotiationConfig(scenario=NegotiationScenario.RENTAL)
        assert config.max_rounds == 10

    def test_max_rounds_range(self):
        with pytest.raises(ValidationError):
            NegotiationConfig(scenario=NegotiationScenario.RENTAL, max_rounds=100)


class TestLLMOfferProposal:
    def test_valid_proposal(self):
        proposal = LLMOfferProposal(
            terms={"salary_lpa": 18, "remote_days": 3},
            reasoning_summary="Competitive offer.",
            concessions=["reduced salary ask"],
            requested_concessions=["remote work"],
        )
        assert proposal.terms["salary_lpa"] == 18


class TestAgreementResult:
    def test_satisfaction_bounds(self):
        with pytest.raises(ValidationError):
            AgreementResult(
                final_terms={},
                party_a_satisfaction=150,  # over 100
                party_b_satisfaction=80,
                fairness_score=85,
                total_rounds=5,
            )

    def test_valid_agreement(self):
        result = AgreementResult(
            final_terms={"rent": 19000},
            party_a_satisfaction=85.5,
            party_b_satisfaction=78.2,
            fairness_score=80.0,
            total_rounds=6,
        )
        assert result.constraint_violations == 0


class TestCreateNegotiationRequest:
    def test_valid_request(self):
        req = CreateNegotiationRequest(
            config=NegotiationConfig(
                scenario=NegotiationScenario.RENTAL,
                party_a_name="Tenant",
                party_b_name="Landlord",
            ),
            party_a_preferences=PartyPreferences(
                hard_constraints={"max_monthly_rent": 20000}
            ),
            party_b_preferences=PartyPreferences(
                hard_constraints={"min_monthly_rent": 18000}
            ),
        )
        assert req.config.scenario == NegotiationScenario.RENTAL
