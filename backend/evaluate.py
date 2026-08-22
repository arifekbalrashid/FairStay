#!/usr/bin/env python3
"""
FairDeal Evaluation Harness — Rental Only

Runs automated test negotiations using the deterministic fallback agent.
Usage: python evaluate.py
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any

sys.path.insert(0, ".")

from app.models.schemas import (
    NegotiationStyle,
    PartyPreferences,
    PartyRole,
    StructuredOffer,
)
from app.negotiation.engine import get_variable_names
from app.negotiation.scorer import NegotiationScorer
from app.negotiation.validator import ConstraintValidator
from app.services.llm_service import DeterministicFallbackAgent


@dataclass
class TestCase:
    name: str
    party_a_prefs: dict[str, Any]
    party_b_prefs: dict[str, Any]
    max_rounds: int = 10
    expected_outcome: str = "agreement"
    description: str = ""


@dataclass
class TestResult:
    name: str
    outcome: str
    rounds: int = 0
    party_a_satisfaction: float = 0.0
    party_b_satisfaction: float = 0.0
    fairness_score: float = 0.0
    constraint_violations: int = 0
    duration_ms: float = 0.0
    expected_outcome: str = ""
    passed: bool = False
    error: str = ""
    final_terms: dict = field(default_factory=dict)


def run_negotiation(test: TestCase) -> TestResult:
    start = time.time()
    variable_names = get_variable_names("rental")

    party_a_prefs = PartyPreferences(**test.party_a_prefs)
    party_b_prefs = PartyPreferences(**test.party_b_prefs)
    a_prefs_dict = party_a_prefs.model_dump()
    b_prefs_dict = party_b_prefs.model_dump()

    offers: list[StructuredOffer] = []
    current_terms: dict | None = None
    agreement_reached = False

    for round_num in range(1, test.max_rounds + 1):
        if round_num == 1:
            a_terms = DeterministicFallbackAgent.generate_initial_offer(
                a_prefs_dict, variable_names, party_a_prefs.negotiation_style.value
            )
        else:
            a_last = None
            for o in reversed(offers):
                if o.party == PartyRole.PARTY_A:
                    a_last = o.terms
                    break
            a_terms = DeterministicFallbackAgent.generate_counteroffer(
                a_prefs_dict, current_terms or {}, a_last,
                round_num, test.max_rounds, variable_names,
                party_a_prefs.negotiation_style.value,
            )

        a_offer = StructuredOffer(round=round_num, party=PartyRole.PARTY_A, terms=a_terms)
        a_valid = ConstraintValidator.validate(a_offer, party_a_prefs)
        if not a_valid.valid:
            continue

        offers.append(a_offer)
        current_terms = a_terms

        b_accept, _ = DeterministicFallbackAgent.evaluate_offer(
            b_prefs_dict, a_terms, round_num, test.max_rounds
        )
        if b_accept:
            b_constraint = ConstraintValidator.validate(a_offer, party_b_prefs)
            if b_constraint.valid:
                agreement_reached = True
                break

        b_last = None
        for o in reversed(offers):
            if o.party == PartyRole.PARTY_B:
                b_last = o.terms
                break
        b_terms = DeterministicFallbackAgent.generate_counteroffer(
            b_prefs_dict, a_terms, b_last,
            round_num, test.max_rounds, variable_names,
            party_b_prefs.negotiation_style.value,
        )

        b_offer = StructuredOffer(round=round_num, party=PartyRole.PARTY_B, terms=b_terms)
        b_valid = ConstraintValidator.validate(b_offer, party_b_prefs)
        if not b_valid.valid:
            continue

        offers.append(b_offer)
        current_terms = b_terms

        a_accept, _ = DeterministicFallbackAgent.evaluate_offer(
            a_prefs_dict, b_terms, round_num, test.max_rounds
        )
        if a_accept:
            a_constraint = ConstraintValidator.validate(b_offer, party_a_prefs)
            if a_constraint.valid:
                agreement_reached = True
                break

    duration = (time.time() - start) * 1000

    if agreement_reached and current_terms:
        score = NegotiationScorer.score_agreement(
            current_terms, party_a_prefs, party_b_prefs,
            total_rounds=len(set(o.round for o in offers)), offers=offers,
        )
        return TestResult(
            name=test.name, outcome="agreement", rounds=score.total_rounds,
            party_a_satisfaction=score.party_a_satisfaction,
            party_b_satisfaction=score.party_b_satisfaction,
            fairness_score=score.fairness_score,
            constraint_violations=score.constraint_violations,
            duration_ms=duration, expected_outcome=test.expected_outcome,
            passed=test.expected_outcome == "agreement", final_terms=current_terms,
        )
    else:
        return TestResult(
            name=test.name, outcome="failure", rounds=test.max_rounds,
            duration_ms=duration, expected_outcome=test.expected_outcome,
            passed=test.expected_outcome == "failure",
            error="No agreement within max rounds",
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test Cases — FairStay Marketplace
# ═══════════════════════════════════════════════════════════════════════════

TEST_CASES: list[TestCase] = [
    TestCase(
        name="easy_overlap",
        description="Wide overlapping range",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 5000, "min_stay_nights": 5},
            "ideal_values": {"nightly_price": 3000, "stay_nights": 7, "total_price": 21000, "deposit": 0, "cleaning_fee": 500, "check_in": "10:00", "check_out": "14:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 5000, "stay_nights": 5, "total_price": 25000, "deposit": 5000, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price", "parking"],
            "negotiation_style": "flexible",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 2500},
            "ideal_values": {"nightly_price": 4500, "stay_nights": 10, "total_price": 45000, "deposit": 10000, "cleaning_fee": 1500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 2500, "stay_nights": 3, "total_price": 7500, "deposit": 5000, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price", "deposit"],
            "negotiation_style": "flexible",
        },
        expected_outcome="agreement",
    ),
    TestCase(
        name="impossible_no_overlap",
        description="Guest max budget < Host min price",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 2000},
            "ideal_values": {"nightly_price": 1500, "stay_nights": 5, "total_price": 7500, "deposit": 0, "cleaning_fee": 0, "check_in": "10:00", "check_out": "14:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 2000, "stay_nights": 5, "total_price": 10000, "deposit": 2000, "cleaning_fee": 500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "firm",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 3000},
            "ideal_values": {"nightly_price": 4000, "stay_nights": 10, "total_price": 40000, "deposit": 10000, "cleaning_fee": 1500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 3000, "stay_nights": 3, "total_price": 9000, "deposit": 5000, "cleaning_fee": 1000, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "aggressive",
        },
        expected_outcome="failure",
    ),
    TestCase(
        name="aggressive_guest",
        description="Aggressive guest vs moderate host",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 4000},
            "ideal_values": {"nightly_price": 2500, "stay_nights": 5, "total_price": 12500, "deposit": 0, "cleaning_fee": 0, "check_in": "10:00", "check_out": "14:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 4000, "stay_nights": 5, "total_price": 20000, "deposit": 5000, "cleaning_fee": 500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price", "parking"],
            "negotiation_style": "aggressive",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 2800},
            "ideal_values": {"nightly_price": 4500, "stay_nights": 7, "total_price": 31500, "deposit": 10000, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 2800, "stay_nights": 3, "total_price": 8400, "deposit": 5000, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price", "stay_nights"],
            "negotiation_style": "moderate",
        },
        expected_outcome="agreement",
    ),
    TestCase(
        name="firm_vs_firm",
        description="Both parties firm",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 3500},
            "ideal_values": {"nightly_price": 2800, "stay_nights": 5, "total_price": 14000, "deposit": 2000, "cleaning_fee": 500, "check_in": "12:00", "check_out": "12:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 3500, "stay_nights": 5, "total_price": 17500, "deposit": 5000, "cleaning_fee": 800, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "firm",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 3200},
            "ideal_values": {"nightly_price": 4000, "stay_nights": 7, "total_price": 28000, "deposit": 8000, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 3200, "stay_nights": 4, "total_price": 12800, "deposit": 4000, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "firm",
        },
        expected_outcome="agreement",
    ),
    TestCase(
        name="narrow_overlap",
        description="Very narrow overlap: 3400-3500",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 3500},
            "ideal_values": {"nightly_price": 2500, "stay_nights": 5, "total_price": 12500, "deposit": 0, "cleaning_fee": 0, "check_in": "10:00", "check_out": "14:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 3500, "stay_nights": 5, "total_price": 17500, "deposit": 5000, "cleaning_fee": 500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "moderate",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 3400},
            "ideal_values": {"nightly_price": 4500, "stay_nights": 7, "total_price": 31500, "deposit": 10000, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 3400, "stay_nights": 3, "total_price": 10200, "deposit": 5000, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "moderate",
        },
        expected_outcome="agreement",
    ),
    TestCase(
        name="demo_scenario",
        description="The built-in demo scenario (seed data)",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 3500, "max_deposit": 10000, "min_stay_nights": 3},
            "soft_preferences": {"parking": True, "cancellation_policy": "flexible"},
            "ideal_values": {"nightly_price": 2500, "stay_nights": 5, "total_price": 12500, "deposit": 0, "cleaning_fee": 0, "check_in": "10:00", "check_out": "14:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 3500, "stay_nights": 3, "total_price": 10500, "deposit": 10000, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price", "parking", "deposit"],
            "negotiation_style": "moderate",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 2800, "min_deposit": 5000, "min_stay_nights": 2},
            "soft_preferences": {"stay_nights": 7, "parking": False},
            "ideal_values": {"nightly_price": 4000, "stay_nights": 7, "total_price": 28000, "deposit": 15000, "cleaning_fee": 1500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 2800, "stay_nights": 2, "total_price": 5600, "deposit": 5000, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price", "stay_nights", "deposit"],
            "negotiation_style": "firm",
        },
        expected_outcome="agreement",
    ),
    TestCase(
        name="max_rounds_3",
        description="Only 3 rounds — tests urgency",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 3200},
            "ideal_values": {"nightly_price": 2500, "stay_nights": 5, "total_price": 12500, "deposit": 0, "cleaning_fee": 0, "check_in": "12:00", "check_out": "12:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 3200, "stay_nights": 5, "total_price": 16000, "deposit": 5000, "cleaning_fee": 500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "moderate",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 2800},
            "ideal_values": {"nightly_price": 3800, "stay_nights": 7, "total_price": 26600, "deposit": 10000, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 2800, "stay_nights": 3, "total_price": 8400, "deposit": 5000, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "moderate",
        },
        max_rounds=3,
        expected_outcome="agreement",
    ),
    TestCase(
        name="both_flexible",
        description="Both flexible — should agree quickly",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 4000},
            "ideal_values": {"nightly_price": 2500, "stay_nights": 5, "total_price": 12500, "deposit": 0, "cleaning_fee": 0, "check_in": "10:00", "check_out": "14:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 4000, "stay_nights": 5, "total_price": 20000, "deposit": 5000, "cleaning_fee": 500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "flexible",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 2500},
            "ideal_values": {"nightly_price": 3500, "stay_nights": 7, "total_price": 24500, "deposit": 8000, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 2500, "stay_nights": 3, "total_price": 7500, "deposit": 4000, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["nightly_price"],
            "negotiation_style": "flexible",
        },
        max_rounds=2,
        expected_outcome="agreement",
    ),
    TestCase(
        name="boolean_focus",
        description="Main disagreement on boolean values",
        party_a_prefs={
            "hard_constraints": {"max_monthly_rent": 22000},
            "ideal_values": {"monthly_rent": 18000, "security_deposit": 30000, "lease_months": 12, "furnished": True, "parking": True, "maintenance_included": True},
            "acceptable_values": {"monthly_rent": 22000, "security_deposit": 45000, "lease_months": 11, "furnished": False, "parking": False, "maintenance_included": False},
            "priorities": ["furnished", "parking", "monthly_rent"],
            "negotiation_style": "moderate",
        },
        party_b_prefs={
            "hard_constraints": {"min_monthly_rent": 17000},
            "ideal_values": {"monthly_rent": 22000, "security_deposit": 45000, "lease_months": 24, "furnished": False, "parking": False, "maintenance_included": False},
            "acceptable_values": {"monthly_rent": 17000, "security_deposit": 30000, "lease_months": 11, "furnished": True, "parking": True, "maintenance_included": True},
            "priorities": ["monthly_rent", "lease_months"],
            "negotiation_style": "moderate",
        },
        expected_outcome="agreement",
    ),
    TestCase(
        name="deposit_conflict",
        description="Deposit constraints conflict while rent overlaps",
        party_a_prefs={
            "hard_constraints": {"max_nightly_price": 3200, "max_deposit": 5000},
            "ideal_values": {"nightly_price": 2500, "deposit": 0, "stay_nights": 5, "total_price": 12500, "cleaning_fee": 0, "check_in": "10:00", "check_out": "14:00", "parking": True, "cancellation_policy": "flexible"},
            "acceptable_values": {"nightly_price": 3200, "deposit": 5000, "stay_nights": 5, "total_price": 16000, "cleaning_fee": 500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            "priorities": ["deposit", "nightly_price"],
            "negotiation_style": "moderate",
        },
        party_b_prefs={
            "hard_constraints": {"min_nightly_price": 2800, "min_deposit": 10000},
            "ideal_values": {"nightly_price": 3800, "deposit": 15000, "stay_nights": 7, "total_price": 26600, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "strict"},
            "acceptable_values": {"nightly_price": 2800, "deposit": 10000, "stay_nights": 3, "total_price": 8400, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            "priorities": ["deposit", "nightly_price"],
            "negotiation_style": "moderate",
        },
        expected_outcome="failure",
    ),
]


def run_all_tests() -> list[TestResult]:
    results = []
    for i, test in enumerate(TEST_CASES, 1):
        print(f"  [{i:2d}/{len(TEST_CASES)}] {test.name}...", end=" ", flush=True)
        try:
            result = run_negotiation(test)
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"{status} ({result.outcome}, {result.rounds}r, {result.duration_ms:.0f}ms)")
            results.append(result)
        except Exception as e:
            print(f"💥 ERROR: {e}")
            results.append(TestResult(name=test.name, outcome="error", expected_outcome=test.expected_outcome, passed=False, error=str(e)))
    return results


def print_summary(results: list[TestResult]):
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    agreements = [r for r in results if r.outcome == "agreement"]

    avg_rounds = sum(r.rounds for r in agreements) / max(len(agreements), 1)
    avg_a_sat = sum(r.party_a_satisfaction for r in agreements) / max(len(agreements), 1)
    avg_b_sat = sum(r.party_b_satisfaction for r in agreements) / max(len(agreements), 1)
    avg_fairness = sum(r.fairness_score for r in agreements) / max(len(agreements), 1)
    total_violations = sum(r.constraint_violations for r in results)

    print("\n" + "═" * 60)
    print("  FAIRSTAY EVALUATION RESULTS (Accommodation)")
    print("═" * 60)
    print(f"\n  Test Cases:              {total}")
    print(f"  Passed:                  {passed}/{total} ({passed/total*100:.0f}%)")
    print(f"  Agreements:              {len(agreements)}")
    print(f"  Constraint Violations:   {total_violations}")
    print(f"  Avg Rounds:              {avg_rounds:.1f}")
    print(f"  Avg Guest Satisfaction:  {avg_a_sat:.1f}%")
    print(f"  Avg Host Satisfaction:   {avg_b_sat:.1f}%")
    print(f"  Avg Fairness:            {avg_fairness:.1f}%")
    print("═" * 60)

    exit_code = 0 if passed == total else 1
    print(f"  EXIT CODE: {exit_code}")
    print("═" * 60)
    return exit_code


if __name__ == "__main__":
    print("\n⚖️  FairStay — Evaluation Harness (Accommodation)")
    print(f"  Running {len(TEST_CASES)} test negotiations...\n")
    results = run_all_tests()
    exit_code = print_summary(results)
    sys.exit(exit_code)

