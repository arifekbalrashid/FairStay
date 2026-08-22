"""Party A agent — uses primary LLM provider (OpenAI by default)."""

from __future__ import annotations

from app.agents.base_agent import NegotiationAgent
from app.models.schemas import PartyPreferences, PartyRole


class PartyAAgent(NegotiationAgent):
    """Agent representing Party A, using the primary LLM provider."""

    def __init__(
        self,
        name: str,
        preferences: PartyPreferences,
        scenario: str,
    ) -> None:
        super().__init__(
            role=PartyRole.PARTY_A,
            name=name,
            preferences=preferences,
            scenario=scenario,
            provider="openai",  # Primary provider
        )
