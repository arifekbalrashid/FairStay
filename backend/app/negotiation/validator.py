"""Deterministic constraint and offer validation — no LLM calls."""

from __future__ import annotations

import structlog
from app.models.schemas import (
    PartyPreferences,
    StructuredOffer,
    ValidationResult,
)

logger = structlog.get_logger()


class ConstraintValidator:
    """Validates an offer against a party's hard constraints."""

    @staticmethod
    def validate(offer: StructuredOffer, preferences: PartyPreferences) -> ValidationResult:
        violations: list[str] = []
        warnings: list[str] = []

        for key, constraint_value in preferences.hard_constraints.items():
            offer_value = offer.terms.get(key)
            if offer_value is None:
                continue

            # Parse constraint format: "min_X", "max_X", or exact match
            if key.startswith("min_"):
                var_name = key[4:]
                actual = offer.terms.get(var_name, offer_value)
                if isinstance(actual, (int, float)) and isinstance(constraint_value, (int, float)):
                    if actual < constraint_value:
                        violations.append(
                            f"{var_name} = {actual} is below minimum {constraint_value}"
                        )
            elif key.startswith("max_"):
                var_name = key[4:]
                actual = offer.terms.get(var_name, offer_value)
                if isinstance(actual, (int, float)) and isinstance(constraint_value, (int, float)):
                    if actual > constraint_value:
                        violations.append(
                            f"{var_name} = {actual} exceeds maximum {constraint_value}"
                        )
            elif isinstance(offer_value, (int, float)) and isinstance(constraint_value, (int, float)):
                # Direct comparison — check if this looks like a max or min based on context
                pass  # handled by the prefixed keys above
            elif isinstance(offer_value, bool) and isinstance(constraint_value, bool):
                if offer_value != constraint_value:
                    violations.append(f"{key} must be {constraint_value}, got {offer_value}")

        # Also validate against the terms directly using the naming convention
        for key, value in offer.terms.items():
            # Check max constraints
            max_key = f"max_{key}"
            if max_key in preferences.hard_constraints:
                limit = preferences.hard_constraints[max_key]
                if isinstance(value, (int, float)) and isinstance(limit, (int, float)):
                    if value > limit:
                        violations.append(
                            f"{key} = {value} exceeds maximum constraint {limit}"
                        )

            # Check min constraints
            min_key = f"min_{key}"
            if min_key in preferences.hard_constraints:
                limit = preferences.hard_constraints[min_key]
                if isinstance(value, (int, float)) and isinstance(limit, (int, float)):
                    if value < limit:
                        violations.append(
                            f"{key} = {value} is below minimum constraint {limit}"
                        )

            # Check boolean constraints
            if key in preferences.hard_constraints:
                constraint = preferences.hard_constraints[key]
                if isinstance(constraint, bool) and isinstance(value, bool):
                    if value != constraint:
                        violations.append(
                            f"{key} must be {constraint}, got {value}"
                        )

        # Soft preference warnings
        for key, pref_value in preferences.soft_preferences.items():
            offer_value = offer.terms.get(key)
            if offer_value is not None and offer_value != pref_value:
                warnings.append(f"{key} = {offer_value} differs from preference {pref_value}")

        valid = len(violations) == 0
        if not valid:
            logger.warning(
                "constraint_violation",
                party=offer.party,
                round=offer.round,
                violations=violations,
            )

        return ValidationResult(valid=valid, violations=violations, warnings=warnings)


class OfferValidator:
    """Validates offer structure and completeness."""

    @staticmethod
    def validate_structure(
        offer: StructuredOffer,
        required_variables: list[str] | None = None,
    ) -> ValidationResult:
        violations: list[str] = []
        warnings: list[str] = []

        if not offer.terms:
            violations.append("Offer contains no terms.")

        if required_variables:
            missing = [v for v in required_variables if v not in offer.terms]
            if missing:
                warnings.append(f"Missing optional variables: {', '.join(missing)}")

        # Check for obviously invalid numeric values
        for key, value in offer.terms.items():
            if isinstance(value, (int, float)):
                if value < 0:
                    violations.append(f"{key} has negative value: {value}")

        return ValidationResult(valid=len(violations) == 0, violations=violations, warnings=warnings)


class AgreementValidator:
    """Validates a final agreement against both parties' constraints."""

    @staticmethod
    def validate(
        final_terms: dict,
        party_a_prefs: PartyPreferences,
        party_b_prefs: PartyPreferences,
    ) -> ValidationResult:
        violations: list[str] = []
        warnings: list[str] = []

        # Create a dummy offer to reuse ConstraintValidator
        from app.models.schemas import PartyRole

        dummy_offer = StructuredOffer(
            round=1,
            party=PartyRole.PARTY_A,
            terms=final_terms,
        )

        # Validate against Party A constraints
        result_a = ConstraintValidator.validate(dummy_offer, party_a_prefs)
        for v in result_a.violations:
            violations.append(f"[Party A] {v}")
        for w in result_a.warnings:
            warnings.append(f"[Party A] {w}")

        # Validate against Party B constraints
        result_b = ConstraintValidator.validate(dummy_offer, party_b_prefs)
        for v in result_b.violations:
            violations.append(f"[Party B] {v}")
        for w in result_b.warnings:
            warnings.append(f"[Party B] {w}")

        return ValidationResult(
            valid=len(violations) == 0,
            violations=violations,
            warnings=warnings,
        )
