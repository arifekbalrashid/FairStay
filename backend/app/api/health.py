"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.services.llm_service import get_llm_service

router = APIRouter()


@router.get("/health")
async def health_check():
    """Return application health status and configured providers."""
    settings = get_settings()
    llm = get_llm_service()

    return {
        "status": "ok",
        "providers": {
            "openai": settings.has_openai,
            "google": settings.has_google,
            "any_available": llm.has_any_provider,
            "available_providers": llm.available_providers,
            "fallback_mode": not llm.has_any_provider,
        },
        "config": {
            "max_rounds": settings.max_rounds,
            "max_retries": settings.max_retries,
        },
    }
