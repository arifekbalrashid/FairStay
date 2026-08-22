"""Party B agent — uses secondary LLM provider (Google by default)."""

from __future__ import annotations

from app.agents.base_agent import NegotiationAgent
from app.models.schemas import PartyPreferences, PartyRole


class PartyBAgent(NegotiationAgent):
    """Agent representing Party B, using the secondary LLM provider."""

    def __init__(
        self,
        name: str,
        preferences: PartyPreferences,
        scenario: str,
    ) -> None:
        super().__init__(
            role=PartyRole.PARTY_B,
            name=name,
            preferences=preferences,
            scenario=scenario,
            provider="google",  # Secondary provider
        )
