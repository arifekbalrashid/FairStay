"""FairDeal — AI Negotiation Platform — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="langchain_google_genai")

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    logger.info("fairdeal_starting", log_level=settings.log_level)

    # Create database tables
    await create_tables()
    logger.info("database_tables_created")

    # Pre-initialize LLM service
    from app.services.llm_service import get_llm_service
    llm = get_llm_service()
    if llm.has_any_provider:
        logger.info("llm_providers_ready", providers=llm.available_providers)
    else:
        logger.warning("no_llm_providers", message="Running in deterministic fallback mode")

    yield

    logger.info("fairdeal_shutdown")


# ─── App ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FairDeal",
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
