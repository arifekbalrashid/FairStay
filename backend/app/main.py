"""FairStay — AI Negotiation Platform — FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="langchain_google_genai")

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import create_tables


# ─── Structured logging setup ──────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ─── Lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    setup_logging(settings.log_level)

    logger = structlog.get_logger()
    logger.info("fairstay_starting", log_level=settings.log_level)

    # Create database tables
    await create_tables()
    logger.info("database_tables_created")

    # Seed if DB is empty (first deploy)
    from app.database import async_session_factory
    from app.models.database_models import PropertyDB
    from sqlalchemy import select
    async with async_session_factory() as session:
        result = await session.execute(select(PropertyDB).limit(1))
        if result.scalars().first() is None:
            logger.info("empty_database_detected", action="auto-seeding")
            from app.seed import seed_properties
            await seed_properties(session)
            logger.info("seed_complete")

    # Pre-initialize LLM service
    from app.services.llm_service import get_llm_service
    llm = get_llm_service()
    if llm.has_any_provider:
        logger.info("llm_providers_ready", providers=llm.available_providers)
    else:
        logger.warning("no_llm_providers", message="Running in deterministic fallback mode")

    yield

    logger.info("fairstay_shutdown")


# ─── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FairStay",
    description="AI-powered multi-agent negotiation platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global exception handler ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = structlog.get_logger()
    logger.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ─── Include routers ──────────────────────────────────────────────────────

from app.api.health import router as health_router
from app.api.negotiations import router as negotiations_router

app.include_router(health_router, tags=["health"])
app.include_router(negotiations_router, tags=["negotiations"])


# ─── Serve Frontend (Production) ──────────────────────────────────────────
# In production, the Vite build output is placed at /app/static.
# We serve it as static files and catch-all for SPA routing.

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if STATIC_DIR.is_dir():
    # Mount /assets for hashed JS/CSS bundles
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    # Serve other static files (favicon, images, etc.)
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Catch-all: serve the file if it exists, otherwise return index.html for SPA routing."""
        file_path = STATIC_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
