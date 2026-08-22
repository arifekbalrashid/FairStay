"""Tests for the deterministic constraint and offer validator."""

import pytest
from app.models.schemas import (
    PartyPreferences,
    PartyRole,
    StructuredOffer,
    NegotiationStyle,
)
from app.negotiation.validator import (
    AgreementValidator,
    ConstraintValidator,
    OfferValidator,
)


# ─── Fixtures ───────────────────────────────────────────────────────────────

def make_tenant_prefs():
    return PartyPreferences(
        hard_constraints={
            "max_monthly_rent": 20000,
            "max_security_deposit": 40000,
            "min_lease_months": 11,
        },
        ideal_values={
            "monthly_rent": 17000,
            "security_deposit": 25000,
            "lease_months": 12,
            "furnished": True,
            "parking": True,
        },
        acceptable_values={
            "monthly_rent": 20000,
            "security_deposit": 40000,
            "lease_months": 11,
        },
        priorities=["monthly_rent", "furnished", "parking"],
        negotiation_style=NegotiationStyle.MODERATE,
    )


def make_landlord_prefs():
    return PartyPreferences(
        hard_constraints={
            "min_monthly_rent": 18000,
            "min_security_deposit": 30000,
            "min_lease_months": 11,
        },
        ideal_values={
            "monthly_rent": 23000,
            "security_deposit": 50000,
            "lease_months": 24,
        },
        acceptable_values={
            "monthly_rent": 18000,
            "security_deposit": 30000,
            "lease_months": 11,
        },
        priorities=["monthly_rent", "lease_months"],
        negotiation_style=NegotiationStyle.FIRM,
    )


def make_offer(terms, party=PartyRole.PARTY_A, round_num=1):
    return StructuredOffer(round=round_num, party=party, terms=terms)


# ─── Constraint Validator Tests ─────────────────────────────────────────────

class TestConstraintValidator:
    def test_valid_offer_within_constraints(self):
        prefs = make_tenant_prefs()
        offer = make_offer({"monthly_rent": 19000, "security_deposit": 35000, "lease_months": 12})
        result = ConstraintValidator.validate(offer, prefs)
        assert result.valid
        assert len(result.violations) == 0

    def test_rent_exceeds_max(self):
        prefs = make_tenant_prefs()
        offer = make_offer({"monthly_rent": 22000})
        result = ConstraintValidator.validate(offer, prefs)
        assert not result.valid
        assert any("monthly_rent" in v for v in result.violations)

    def test_deposit_exceeds_max(self):
        prefs = make_tenant_prefs()
        offer = make_offer({"security_deposit": 50000})
        result = ConstraintValidator.validate(offer, prefs)
        assert not result.valid

    def test_lease_below_min(self):
        prefs = make_tenant_prefs()
        offer = make_offer({"lease_months": 6})
        result = ConstraintValidator.validate(offer, prefs)
        assert not result.valid

    def test_landlord_rent_below_min(self):
        prefs = make_landlord_prefs()
        offer = make_offer({"monthly_rent": 15000})
        result = ConstraintValidator.validate(offer, prefs)
        assert not result.valid

    def test_multiple_violations(self):
        prefs = make_tenant_prefs()
        offer = make_offer({"monthly_rent": 25000, "security_deposit": 60000})
        result = ConstraintValidator.validate(offer, prefs)
        assert not result.valid
        assert len(result.violations) >= 2

    def test_exactly_at_limit_is_valid(self):
        prefs = make_tenant_prefs()
        offer = make_offer({"monthly_rent": 20000})
        result = ConstraintValidator.validate(offer, prefs)
        assert result.valid

    def test_boolean_constraint(self):
        prefs = PartyPreferences(hard_constraints={"parking": True})
        offer = make_offer({"parking": False})
        result = ConstraintValidator.validate(offer, prefs)
        assert not result.valid


# ─── Offer Validator Tests ──────────────────────────────────────────────────

class TestOfferValidator:
    def test_valid_offer_structure(self):
        offer = make_offer({"rent": 19000, "deposit": 30000})
        result = OfferValidator.validate_structure(offer)
        assert result.valid

    def test_empty_terms(self):
        offer = make_offer({})
        result = OfferValidator.validate_structure(offer)
        assert not result.valid

    def test_negative_value(self):
        offer = make_offer({"rent": -5000})
        result = OfferValidator.validate_structure(offer)
        assert not result.valid


# ─── Agreement Validator Tests ──────────────────────────────────────────────

class TestAgreementValidator:
    def test_valid_agreement(self):
        """Terms that satisfy both parties' constraints."""
        terms = {
            "monthly_rent": 19000,
            "security_deposit": 35000,
            "lease_months": 12,
        }
        result = AgreementValidator.validate(
            terms, make_tenant_prefs(), make_landlord_prefs()
        )
        assert result.valid
        assert len(result.violations) == 0

    def test_impossible_agreement(self):
        """Terms where tenant max < landlord min should fail validation on at least one side."""
        terms = {"monthly_rent": 17000}  # below landlord min of 18000
        result = AgreementValidator.validate(
            terms, make_tenant_prefs(), make_landlord_prefs()
        )
        assert not result.valid

    def test_agreement_violates_party_a(self):
        terms = {"monthly_rent": 22000, "security_deposit": 50000, "lease_months": 12}
        result = AgreementValidator.validate(
            terms, make_tenant_prefs(), make_landlord_prefs()
        )
        assert not result.valid
        assert any("[Party A]" in v for v in result.violations)
