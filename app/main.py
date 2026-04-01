"""
AP Sachivalayam AI Copilot — FastAPI Application

Telugu-first WhatsApp AI assistant for AP's 1.3L village secretariat employees.
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app

from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.dependencies import async_session_factory, engine, redis_client

logger = structlog.get_logger()
settings = get_settings()

# Prometheus metrics
REQUEST_COUNT = Counter("sachivalayam_requests_total", "Total requests", ["method", "endpoint"])
RESPONSE_TIME = Histogram("sachivalayam_response_seconds", "Response time", ["endpoint"])
WHATSAPP_MESSAGES = Counter("sachivalayam_wa_messages_total", "WhatsApp messages", ["direction"])
LLM_CALLS = Counter("sachivalayam_llm_calls_total", "LLM API calls", ["model", "task_type"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info(
        "Starting AP Sachivalayam AI Copilot",
        env=settings.app_env,
        version="0.1.0",
    )

    # Startup: warm FAQ cache
    try:
        await _warm_faq_cache()
    except Exception as e:
        logger.warning("FAQ cache warming failed (non-fatal)", error=str(e))

    # Startup: verify database connection
    try:
        from sqlalchemy import text
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error("Database connection failed", error=str(e))

    # Startup: verify Redis connection
    try:
        await redis_client.ping()
        logger.info("Redis connection verified")
    except Exception as e:
        logger.warning("Redis connection failed (non-fatal)", error=str(e))

    logger.info("Startup complete — ready to serve")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await engine.dispose()
    await redis_client.aclose()
    logger.info("Shutdown complete")


async def _warm_faq_cache():
    """Pre-load top FAQs into Redis cache on startup."""
    async with async_session_factory() as session:
        from app.services.scheme_advisor import SchemeAdvisor
        advisor = SchemeAdvisor(db=session)
        count = await advisor.warm_faq_cache()
        logger.info("FAQ cache warmed on startup", count=count)


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description=(
        "AI Copilot for AP Village Secretariat Employees.\n\n"
        "Telugu-first, WhatsApp-based assistant for scheme queries, "
        "form automation, and citizen services.\n\n"
        "**30 schemes** | **10 form templates** | **Voice input** | **Offline support**"
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (Redis-backed)
from app.core.rate_limiter import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# API routes
app.include_router(api_v1_router, prefix="/api/v1")

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint — app info."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
