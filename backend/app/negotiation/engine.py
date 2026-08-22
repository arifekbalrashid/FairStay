"""Scenario definitions, variable metadata, and seed data for negotiations."""

from __future__ import annotations

from app.models.schemas import (
    NegotiationScenario,
    NegotiationStyle,
    PartyPreferences,
    ScenarioMetadata,
    VariableMetadata,
)


# ─── Scenario Definitions ──────────────────────────────────────────────────

SCENARIOS: dict[NegotiationScenario, ScenarioMetadata] = {
    NegotiationScenario.RENTAL: ScenarioMetadata(
        name=NegotiationScenario.RENTAL,
        display_name="Rental Negotiation",
        description="Negotiate an apartment rental between a tenant and host.",
        party_a_label="Tenant",
        party_b_label="Host",
        variables=[
            VariableMetadata(name="nightly_price", display_name="Nightly Price", type="number", unit="₹", min_value=1000, max_value=50000, description="Price per night"),
            VariableMetadata(name="stay_nights", display_name="Length of Stay", type="number", unit="nights", min_value=1, max_value=30, description="Number of nights to book"),
            VariableMetadata(name="total_price", display_name="Total Price", type="number", unit="₹", min_value=1000, max_value=500000, description="Total price for the stay (nightly * nights)"),
            VariableMetadata(name="deposit", display_name="Security Deposit", type="number", unit="₹", min_value=0, max_value=50000, description="Refundable deposit"),
            VariableMetadata(name="cleaning_fee", display_name="Cleaning Fee", type="number", unit="₹", min_value=0, max_value=5000, description="One-time cleaning fee"),
            VariableMetadata(name="check_in", display_name="Check-in Time", type="string", description="e.g. 15:00 or flexible"),
            VariableMetadata(name="check_out", display_name="Check-out Time", type="string", description="e.g. 11:00 or flexible"),
            VariableMetadata(name="parking", display_name="Parking Included", type="boolean", description="Whether parking is included"),
            VariableMetadata(name="cancellation_policy", display_name="Cancellation Policy", type="string", description="e.g. strict, moderate, flexible"),
        ],
        default_party_a=PartyPreferences(
            hard_constraints={"max_nightly_price": 4000, "min_stay_nights": 5, "max_total_price": 20000},
            soft_preferences={"parking": True, "check_in": "flexible", "check_out": "late"},
            ideal_values={"nightly_price": 3000, "stay_nights": 5, "total_price": 15000, "deposit": 0, "cleaning_fee": 0, "check_in": "10:00", "check_out": "14:00", "parking": True, "cancellation_policy": "flexible"},
            acceptable_values={"nightly_price": 4000, "stay_nights": 5, "total_price": 20000, "deposit": 5000, "cleaning_fee": 500, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            priorities=["total_price", "nightly_price", "parking"],
            negotiation_style=NegotiationStyle.MODERATE,
            private_information="I'm traveling with family and prefer early check-in, but budget is my primary concern.",
        ),
        default_party_b=PartyPreferences(
            hard_constraints={"min_nightly_price": 3200, "min_stay_nights": 2, "cancellation_policy": "moderate"},
            soft_preferences={"stay_nights": 7},
            ideal_values={"nightly_price": 4500, "stay_nights": 7, "total_price": 31500, "deposit": 10000, "cleaning_fee": 1000, "check_in": "15:00", "check_out": "11:00", "parking": False, "cancellation_policy": "moderate"},
            acceptable_values={"nightly_price": 3200, "stay_nights": 2, "total_price": 6400, "deposit": 5000, "cleaning_fee": 500, "check_in": "flexible", "check_out": "flexible", "parking": True, "cancellation_policy": "moderate"},
            priorities=["nightly_price", "stay_nights", "deposit"],
            negotiation_style=NegotiationStyle.FIRM,
            private_information="I need to maximize revenue, but I am willing to offer parking and flexible check-in if the guest stays longer.",
        ),
    ),
}


def get_scenario(scenario: NegotiationScenario) -> ScenarioMetadata:
    """Return scenario metadata by enum value."""
    return SCENARIOS[scenario]


def get_all_scenarios() -> list[ScenarioMetadata]:
    """Return all available scenarios."""
    return list(SCENARIOS.values())


def get_variable_names(scenario: NegotiationScenario) -> list[str]:
    """Return the list of negotiation variable names for a scenario."""
    if isinstance(scenario, str):
        scenario = NegotiationScenario(scenario)
    return [v.name for v in SCENARIOS[scenario].variables]
