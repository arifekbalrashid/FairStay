"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """FairDeal application settings."""

    # --- LLM providers ---
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    google_api_key: Optional[str] = None
    google_model: str = "gemini-3.6-flash"
    groq_api_key: Optional[str] = None
    groq_model: str = "qwen/qwen3.6-27b"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./fairdeal.db"

    # --- Negotiation ---
    max_rounds: int = 10
    max_retries: int = 3

    # --- Server ---
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    # --- Cost estimation (per 1M tokens) ---
    openai_input_cost_per_m: float = 0.15
    openai_output_cost_per_m: float = 0.60
    google_input_cost_per_m: float = 0.075
    google_output_cost_per_m: float = 0.30
    groq_input_cost_per_m: float = 0.59
    groq_output_cost_per_m: float = 0.79

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # ------------------------------------------------------------------
    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_google(self) -> bool:
        return bool(self.google_api_key)

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_any_llm(self) -> bool:
        return self.has_openai or self.has_google or self.has_groq

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
