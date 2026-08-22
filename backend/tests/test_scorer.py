"""Tests for the deterministic scoring system."""

import pytest
from app.models.schemas import (
    PartyPreferences,
    PartyRole,
    StructuredOffer,
    NegotiationStyle,
)
from app.negotiation.scorer import NegotiationScorer


def make_tenant_prefs():
    return PartyPreferences(
        hard_constraints={"max_monthly_rent": 20000},
        ideal_values={"monthly_rent": 17000, "security_deposit": 25000, "lease_months": 12, "furnished": True, "parking": True},
        acceptable_values={"monthly_rent": 20000, "security_deposit": 40000, "lease_months": 11, "furnished": False, "parking": False},
        priorities=["monthly_rent", "furnished", "parking", "security_deposit"],
        negotiation_style=NegotiationStyle.MODERATE,
    )


def make_landlord_prefs():
    return PartyPreferences(
        hard_constraints={"min_monthly_rent": 18000},
        ideal_values={"monthly_rent": 23000, "security_deposit": 50000, "lease_months": 24},
        acceptable_values={"monthly_rent": 18000, "security_deposit": 30000, "lease_months": 11},
        priorities=["monthly_rent", "lease_months"],
        negotiation_style=NegotiationStyle.FIRM,
    )


class TestPartySatisfaction:
    def test_ideal_values_give_100(self):
        prefs = make_tenant_prefs()
        terms = {"monthly_rent": 17000, "security_deposit": 25000, "lease_months": 12, "furnished": True, "parking": True}
        score = NegotiationScorer.calculate_party_satisfaction(terms, prefs)
        assert score == 100.0

    def test_acceptable_values_give_low_score(self):
        prefs = make_tenant_prefs()
        terms = {"monthly_rent": 20000, "security_deposit": 40000, "lease_months": 11, "furnished": False, "parking": False}
        score = NegotiationScorer.calculate_party_satisfaction(terms, prefs)
        assert score < 50

    def test_midpoint_values_give_moderate_score(self):
        prefs = make_tenant_prefs()
        terms = {"monthly_rent": 18500, "security_deposit": 32500, "lease_months": 12}
        score = NegotiationScorer.calculate_party_satisfaction(terms, prefs)
        assert 50 < score < 90

    def test_empty_terms_give_zero(self):
        prefs = make_tenant_prefs()
        score = NegotiationScorer.calculate_party_satisfaction({}, prefs)
        assert score == 0.0

    def test_better_than_ideal_gives_100(self):
        prefs = make_tenant_prefs()
        terms = {"monthly_rent": 15000}  # lower is better for tenant, below ideal
        score = NegotiationScorer.calculate_party_satisfaction(terms, prefs)
        assert score == 100.0


class TestFairness:
    def test_equal_satisfaction_is_fair(self):
        fairness = NegotiationScorer.calculate_fairness(80, 80)
        assert fairness == 80.0

    def test_large_imbalance_is_penalized(self):
        fairness = NegotiationScorer.calculate_fairness(90, 40)
        avg = (90 + 40) / 2  # 65
        assert fairness < avg

    def test_perfect_fairness(self):
        fairness = NegotiationScorer.calculate_fairness(100, 100)
        assert fairness == 100.0


class TestAgreementScoring:
    def test_full_scoring(self):
        terms = {"monthly_rent": 19000, "security_deposit": 35000, "lease_months": 12}
        result = NegotiationScorer.score_agreement(
            terms, make_tenant_prefs(), make_landlord_prefs(), total_rounds=5
        )
        assert result.party_a_satisfaction > 0
        assert result.party_b_satisfaction > 0
        assert result.fairness_score > 0
        assert result.total_rounds == 5
        assert result.constraint_violations == 0

    def test_scoring_with_offers(self):
        terms = {"monthly_rent": 19000}
        offers = [
            StructuredOffer(round=1, party=PartyRole.PARTY_A, terms={"monthly_rent": 17000}, concessions=["rent increased"]),
            StructuredOffer(round=2, party=PartyRole.PARTY_B, terms={"monthly_rent": 22000}, concessions=["rent decreased"]),
        ]
        result = NegotiationScorer.score_agreement(
            terms, make_tenant_prefs(), make_landlord_prefs(), total_rounds=3, offers=offers
        )
        assert result.total_concessions_a == 1
        assert result.total_concessions_b == 1
