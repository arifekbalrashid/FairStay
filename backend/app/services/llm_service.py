"""LLM service — configurable provider, structured output, retry, fallback, cost tracking."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Type, TypeVar

import structlog
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.models.schemas import CostMetrics

logger = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)


class LLMService:
    """Manages LLM providers with retry, fallback, and cost tracking."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._models: dict[str, BaseChatModel] = {}
        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize available LLM providers."""
        if self._settings.has_openai:
            try:
                from langchain_openai import ChatOpenAI

                self._models["openai"] = ChatOpenAI(
                    model=self._settings.openai_model,
                    api_key=self._settings.openai_api_key,
                    temperature=0.7,
                    max_retries=0,  # We handle retries ourselves
                )
                logger.info("llm_provider_initialized", provider="openai", model=self._settings.openai_model)
            except Exception as e:
                logger.error("llm_provider_failed", provider="openai", error=str(e))

        if self._settings.has_google:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                self._models["google"] = ChatGoogleGenerativeAI(
                    model=self._settings.google_model,
                    google_api_key=self._settings.google_api_key,
                    temperature=0.7,
                )
                logger.info("llm_provider_initialized", provider="google", model=self._settings.google_model)
            except Exception as e:
                logger.error("llm_provider_failed", provider="google", error=str(e))

        if self._settings.has_groq:
            try:
                from langchain_groq import ChatGroq

                self._models["groq"] = ChatGroq(
                    model=self._settings.groq_model,
                    api_key=self._settings.groq_api_key,
                    temperature=0.7,
                    max_retries=0,
                )
                logger.info("llm_provider_initialized", provider="groq", model=self._settings.groq_model)
            except Exception as e:
                logger.error("llm_provider_failed", provider="groq", error=str(e))

    @property
    def available_providers(self) -> list[str]:
        return list(self._models.keys())

    @property
    def has_any_provider(self) -> bool:
        return len(self._models) > 0

    def get_model(self, provider: str | None = None) -> BaseChatModel | None:
        """Get a specific model or the first available one."""
        if provider and provider in self._models:
            return self._models[provider]
        if self._models:
            return next(iter(self._models.values()))
        return None

    def get_provider_for_party(self, party_role: str) -> tuple[str, BaseChatModel | None]:
        """
        Assign different models to different parties when possible.
        Party A → first provider (OpenAI), Party B → second provider (Google).
        Falls back to the same model if only one is available.
        """
        providers = list(self._models.keys())
        if not providers:
            return ("fallback", None)

        if len(providers) >= 2:
            if party_role == "party_a":
                return (providers[0], self._models[providers[0]])
            else:
                return (providers[1], self._models[providers[1]])
        else:
            return (providers[0], self._models[providers[0]])

    async def invoke_structured(
        self,
        prompt: str,
        output_schema: Type[T],
        provider: str | None = None,
        party_role: str = "",
    ) -> tuple[T, CostMetrics]:
        """
        Invoke an LLM with structured output. Retries with exponential backoff,
        then falls back to alternate provider.

        Returns (parsed_result, cost_metrics).
        """
        max_retries = self._settings.max_retries

        # Determine primary and fallback providers
        if provider:
            primary_provider = provider
        elif party_role:
            primary_provider, _ = self.get_provider_for_party(party_role)
        else:
            primary_provider = list(self._models.keys())[0] if self._models else "fallback"

        providers_to_try = [primary_provider]
        # Add fallback providers
        for p in self._models:
            if p not in providers_to_try:
                providers_to_try.append(p)

        last_error: Exception | None = None

        for prov in providers_to_try:
            model = self._models.get(prov)
            if model is None:
                continue

            for attempt in range(max_retries):
                try:
                    start_time = time.time()
                    structured_model = model.with_structured_output(output_schema)
                    result = await structured_model.ainvoke(prompt)
                    latency = (time.time() - start_time) * 1000

                    # Estimate tokens (rough approximation)
                    input_tokens = len(prompt) // 4
                    output_tokens = len(result.model_dump_json()) // 4

                    # Calculate cost
                    if prov == "openai":
                        cost = (
                            input_tokens * self._settings.openai_input_cost_per_m / 1_000_000
                            + output_tokens * self._settings.openai_output_cost_per_m / 1_000_000
                        )
                        model_name = self._settings.openai_model
                    elif prov == "google":
                        cost = (
                            input_tokens * self._settings.google_input_cost_per_m / 1_000_000
                            + output_tokens * self._settings.google_output_cost_per_m / 1_000_000
                        )
                        model_name = self._settings.google_model
                    elif prov == "groq":
                        cost = (
                            input_tokens * self._settings.groq_input_cost_per_m / 1_000_000
                            + output_tokens * self._settings.groq_output_cost_per_m / 1_000_000
                        )
                        model_name = self._settings.groq_model
                    else:
                        cost = 0.0
                        model_name = "unknown"

                    metrics = CostMetrics(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost=round(cost, 6),
                        latency_ms=round(latency, 1),
                        model=model_name,
                    )

                    logger.info(
                        "llm_invocation_success",
                        provider=prov,
                        model=model_name,
                        latency_ms=metrics.latency_ms,
                        attempt=attempt + 1,
                    )

                    return result, metrics

                except Exception as e:
                    last_error = e
                    wait_time = 2 ** attempt
                    logger.warning(
                        "llm_invocation_retry",
                        provider=prov,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                        wait_seconds=wait_time,
                    )
                    await asyncio.sleep(wait_time)

            logger.error("llm_provider_exhausted", provider=prov)

        raise RuntimeError(
            f"All LLM providers failed after retries. Last error: {last_error}"
        )


# ─── Deterministic Fallback Agent ──────────────────────────────────────────

class DeterministicFallbackAgent:
    """
    Rule-based fallback for when no LLM is configured.
    Makes reasonable concessions based on simple heuristics.
    """

    @staticmethod
    def generate_initial_offer(
        preferences: dict[str, Any],
        variable_names: list[str],
        negotiation_style: str = "moderate",
    ) -> dict[str, Any]:
        """Generate an initial offer starting from ideal values with a style-based buffer."""
        terms: dict[str, Any] = {}
        ideal = preferences.get("ideal_values", {})
        acceptable = preferences.get("acceptable_values", {})
        hard = preferences.get("hard_constraints", {})

        # How aggressively to start (0 = at ideal, 1 = at acceptable)
        style_factor = {
            "aggressive": 0.0,
            "firm": 0.1,
            "moderate": 0.2,
            "flexible": 0.35,
        }.get(negotiation_style, 0.2)

        for var in variable_names:
            ideal_val = ideal.get(var)
            accept_val = acceptable.get(var)

            if ideal_val is not None:
                if isinstance(ideal_val, bool):
                    terms[var] = ideal_val
                elif isinstance(ideal_val, (int, float)) and accept_val is not None:
                    # Move slightly from ideal toward acceptable
                    move = (accept_val - ideal_val) * style_factor
                    val = ideal_val + move
                    terms[var] = round(val) if isinstance(ideal_val, int) else round(val, 2)
                else:
                    terms[var] = ideal_val
            elif accept_val is not None:
                terms[var] = accept_val

        return terms

    @staticmethod
    def generate_counteroffer(
        preferences: dict[str, Any],
        current_offer_terms: dict[str, Any],
        own_last_terms: dict[str, Any] | None,
        round_number: int,
        max_rounds: int,
        variable_names: list[str],
        negotiation_style: str = "moderate",
    ) -> dict[str, Any]:
        """Generate a counteroffer by making concessions on lower-priority items."""
        ideal = preferences.get("ideal_values", {})
        acceptable = preferences.get("acceptable_values", {})
        priorities = preferences.get("priorities", [])
        hard = preferences.get("hard_constraints", {})

        # Urgency increases as rounds progress
        urgency = min(round_number / max(max_rounds - 1, 1), 1.0)
        style_concession = {
            "aggressive": 0.15,
            "firm": 0.25,
            "moderate": 0.35,
            "flexible": 0.5,
        }.get(negotiation_style, 0.35)

        concession_rate = style_concession + urgency * 0.3

        base = own_last_terms if own_last_terms else {}
        terms: dict[str, Any] = {}

        for var in variable_names:
            ideal_val = ideal.get(var)
            accept_val = acceptable.get(var)
            other_val = current_offer_terms.get(var)
            own_val = base.get(var, ideal_val)

            if own_val is None:
                if other_val is not None:
                    terms[var] = other_val
                continue

            if isinstance(own_val, bool):
                # On booleans, concede if it's not high priority and we're past round 3
                if var not in priorities[:2] and round_number > 3 and other_val is not None:
                    terms[var] = other_val
                else:
                    terms[var] = own_val
                continue

            if isinstance(own_val, (int, float)) and other_val is not None and isinstance(other_val, (int, float)):
                # Priority affects how much we concede
                priority_rank = priorities.index(var) if var in priorities else len(priorities)
                priority_factor = 1.0 - (priority_rank / max(len(priorities), 1)) * 0.5

                # Move toward the other party's position
                move = (other_val - own_val) * concession_rate * (1.0 - priority_factor * 0.5)
                new_val = own_val + move

                # Enforce hard constraints
                max_key = f"max_{var}"
                min_key = f"min_{var}"
                if max_key in hard and new_val > hard[max_key]:
                    new_val = hard[max_key]
                if min_key in hard and new_val < hard[min_key]:
                    new_val = hard[min_key]

                terms[var] = round(new_val) if isinstance(ideal_val, int) else round(new_val, 2)
            else:
                terms[var] = own_val

        return terms

    @staticmethod
    def evaluate_offer(
        preferences: dict[str, Any],
        offer_terms: dict[str, Any],
        round_number: int,
        max_rounds: int,
    ) -> tuple[bool, str]:
        """Evaluate whether to accept an offer. Returns (accept, reasoning)."""
        ideal = preferences.get("ideal_values", {})
        acceptable = preferences.get("acceptable_values", {})
        hard = preferences.get("hard_constraints", {})

        # Check hard constraint violations
        for key, limit in hard.items():
            if key.startswith("max_"):
                var = key[4:]
                val = offer_terms.get(var)
                if val is not None and isinstance(val, (int, float)) and val > limit:
                    return False, f"{var} exceeds hard constraint maximum of {limit}"
            elif key.startswith("min_"):
                var = key[4:]
                val = offer_terms.get(var)
                if val is not None and isinstance(val, (int, float)) and val < limit:
                    return False, f"{var} is below hard constraint minimum of {limit}"

        # Score the offer
        total_score = 0
        count = 0
        for var, ideal_val in ideal.items():
            offer_val = offer_terms.get(var)
            accept_val = acceptable.get(var)
            if offer_val is None or ideal_val is None:
                continue

            if isinstance(ideal_val, bool):
                total_score += 100 if offer_val == ideal_val else 40
                count += 1
                continue

            if isinstance(ideal_val, (int, float)) and isinstance(offer_val, (int, float)):
                if accept_val is not None:
                    ideal_f = float(ideal_val)
                    accept_f = float(accept_val)
                    offer_f = float(offer_val)
                    if ideal_f == accept_f:
                        total_score += 100 if offer_f == ideal_f else 50
                    else:
                        if ideal_f < accept_f:
                            ratio = max(0, min(1, (accept_f - offer_f) / (accept_f - ideal_f)))
                        else:
                            ratio = max(0, min(1, (offer_f - accept_f) / (ideal_f - accept_f)))
                        total_score += 30 + ratio * 70
                    count += 1

        avg_score = total_score / max(count, 1)

        # Accept threshold decreases as rounds progress (more willing to settle)
        urgency = round_number / max(max_rounds, 1)
        threshold = 65 - urgency * 20  # 65 → 45 over rounds

        accept = avg_score >= threshold
        if accept:
            reasoning = f"Offer is acceptable with satisfaction score of {avg_score:.0f}%."
        else:
            reasoning = f"Offer satisfaction is {avg_score:.0f}%, below threshold of {threshold:.0f}%."

        return accept, reasoning


# ─── Singleton ──────────────────────────────────────────────────────────────

_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
