"""Deterministic scoring system for negotiation outcomes — no LLM calls."""

from __future__ import annotations

from app.models.schemas import (
    AgreementResult,
    PartyPreferences,
    StructuredOffer,
)


class NegotiationScorer:
    """Calculates satisfaction and fairness scores deterministically."""

    @staticmethod
    def calculate_party_satisfaction(
        terms: dict,
        preferences: PartyPreferences,
    ) -> float:
        """
        Calculate satisfaction score (0-100) for a party based on how
        close the final terms are to their ideal values.

        Strategy:
        - For each term with an ideal and acceptable value, score is
          proportional to position within the range.
        - Terms matching ideal = 100, matching acceptable = 50, between = interpolated.
        - Terms matching priorities get higher weight.
        """
        if not terms:
            return 0.0

        scores: list[float] = []
        weights: list[float] = []

        priority_map = {p: len(preferences.priorities) - i for i, p in enumerate(preferences.priorities)}

        for key, value in terms.items():
            ideal = preferences.ideal_values.get(key)
            acceptable = preferences.acceptable_values.get(key)

            if ideal is None and acceptable is None:
                continue

            # Weight based on priority
            weight = priority_map.get(key, 1.0)
            weights.append(weight)

            if isinstance(value, bool):
                if ideal is not None:
                    scores.append(100.0 if value == ideal else 30.0)
                else:
                    scores.append(70.0)
                continue

            if not isinstance(value, (int, float)):
                # Non-numeric, non-boolean — simple match check
                if ideal is not None:
                    scores.append(100.0 if value == ideal else 50.0)
                else:
                    scores.append(70.0)
                continue

            # Numeric scoring
            if ideal is not None and acceptable is not None:
                ideal_f = float(ideal)
                acceptable_f = float(acceptable)
                value_f = float(value)

                if ideal_f == acceptable_f:
                    scores.append(100.0 if value_f == ideal_f else 50.0)
                    continue

                # Determine direction: is lower or higher better?
                # If ideal < acceptable, lower is better (e.g., rent for tenant)
                # If ideal > acceptable, higher is better (e.g., salary for candidate)
                if ideal_f < acceptable_f:
                    # Lower is better
                    if value_f <= ideal_f:
                        scores.append(100.0)
                    elif value_f >= acceptable_f:
                        scores.append(30.0)
                    else:
                        ratio = (acceptable_f - value_f) / (acceptable_f - ideal_f)
                        scores.append(30.0 + ratio * 70.0)
                else:
                    # Higher is better
                    if value_f >= ideal_f:
                        scores.append(100.0)
                    elif value_f <= acceptable_f:
                        scores.append(30.0)
                    else:
                        ratio = (value_f - acceptable_f) / (ideal_f - acceptable_f)
                        scores.append(30.0 + ratio * 70.0)

            elif ideal is not None:
                ideal_f = float(ideal)
                value_f = float(value)
                if value_f == ideal_f:
                    scores.append(100.0)
                else:
                    diff_ratio = abs(value_f - ideal_f) / max(abs(ideal_f), 1)
                    scores.append(max(0.0, 100.0 - diff_ratio * 100.0))

            elif acceptable is not None:
                scores.append(60.0)  # At least acceptable but we don't know ideal

        if not scores:
            return 50.0  # No data to score

        total_weight = sum(weights)
        if total_weight == 0:
            return 50.0

        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        return round(min(100.0, max(0.0, weighted_sum / total_weight)), 1)

    @staticmethod
    def calculate_fairness(
        party_a_satisfaction: float,
        party_b_satisfaction: float,
    ) -> float:
        """
        Fairness = average satisfaction, penalized for large imbalance.

        A deal where both parties get 80% is fairer than one where A gets
        95% and B gets 50%.
        """
        avg = (party_a_satisfaction + party_b_satisfaction) / 2
        imbalance = abs(party_a_satisfaction - party_b_satisfaction)
        penalty = imbalance * 0.15  # Penalize up to 15 points for max imbalance
        return round(max(0.0, min(100.0, avg - penalty)), 1)

    @staticmethod
    def score_agreement(
        final_terms: dict,
        party_a_prefs: PartyPreferences,
        party_b_prefs: PartyPreferences,
        total_rounds: int,
        offers: list[StructuredOffer] | None = None,
    ) -> AgreementResult:
        """Calculate full agreement scoring."""
        party_a_sat = NegotiationScorer.calculate_party_satisfaction(
            final_terms, party_a_prefs
        )
        party_b_sat = NegotiationScorer.calculate_party_satisfaction(
            final_terms, party_b_prefs
        )
        fairness = NegotiationScorer.calculate_fairness(party_a_sat, party_b_sat)

        # Count concessions
        total_a = 0
        total_b = 0
        if offers:
            for offer in offers:
                if offer.party.value == "party_a":
                    total_a += len(offer.concessions)
                else:
                    total_b += len(offer.concessions)

        # Check constraint violations
        from app.negotiation.validator import AgreementValidator

        result = AgreementValidator.validate(final_terms, party_a_prefs, party_b_prefs)
        violations = len(result.violations)

        return AgreementResult(
            final_terms=final_terms,
            party_a_satisfaction=party_a_sat,
            party_b_satisfaction=party_b_sat,
            fairness_score=fairness,
            constraint_violations=violations,
            total_rounds=total_rounds,
            total_concessions_a=total_a,
            total_concessions_b=total_b,
        )
