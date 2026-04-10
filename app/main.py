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

    # Startup: create database tables + seed data (idempotent)
    try:
        await _init_database()
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))

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


async def _init_database():
    """Create all tables and seed scheme data on first startup.

    Idempotent — safe to run on every startup. Uses Base.metadata.create_all
    instead of Alembic migrations so it works out-of-the-box on cloud platforms.
    """
    from sqlalchemy import select

    from app.models import Base, Scheme

    # Create tables if they don't exist
    async with engine.begin() as conn:
        # Enable pgvector extension (safe if already enabled)
        try:
            from sqlalchemy import text
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as e:
            logger.warning("pgvector extension not available", error=str(e))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")

    # Check if schemes already seeded
    async with async_session_factory() as session:
        result = await session.execute(select(Scheme).limit(1))
        if result.scalar_one_or_none() is not None:
            logger.info("Database already seeded, skipping")
            return

    # Seed schemes from JSON files
    logger.info("Seeding database...")
    import json
    from pathlib import Path

    schemes_dir = Path(__file__).parent / "data" / "schemes"
    templates_file = Path(__file__).parent / "data" / "templates" / "form_templates.json"
    faqs_file = Path(__file__).parent / "data" / "scheme_faqs.json"

    async with async_session_factory() as session:
        from app.models import FormTemplate, Scheme, SchemeFAQ

        # Load schemes
        scheme_count = 0
        scheme_by_code = {}
        for scheme_file in sorted(schemes_dir.glob("*.json")):
            try:
                with open(scheme_file, encoding="utf-8") as f:
                    data = json.load(f)
                scheme = Scheme(
                    scheme_code=data["scheme_code"],
                    state_code=data.get("state_code", "AP"),
                    name_te=data.get("name_te", ""),
                    name_en=data.get("name_en", ""),
                    department=data.get("department", "General"),
                    description_te=data.get("description_te"),
                    description_en=data.get("description_en"),
                    eligibility_criteria=data.get("eligibility_criteria", {}),
                    required_documents=data.get("required_documents"),
                    benefit_amount=data.get("benefit_amount"),
                    application_process_te=data.get("application_process_te"),
                    go_reference=data.get("go_reference"),
                    is_active=data.get("is_active", True),
                )
                session.add(scheme)
                scheme_by_code[data["scheme_code"]] = scheme
                scheme_count += 1
            except Exception as e:
                logger.warning("Failed to seed scheme", file=str(scheme_file), error=str(e))
        await session.flush()
        logger.info("Seeded schemes", count=scheme_count)

        # Load FAQs
        faq_count = 0
        if faqs_file.exists():
            try:
                with open(faqs_file, encoding="utf-8") as f:
                    faqs_data = json.load(f)
                for scheme_code, faqs_list in faqs_data.items():
                    scheme = scheme_by_code.get(scheme_code)
                    if not scheme or not isinstance(faqs_list, list):
                        continue
                    for faq in faqs_list:
                        session.add(SchemeFAQ(
                            scheme_id=scheme.id,
                            question_te=faq.get("question_te", ""),
                            answer_te=faq.get("answer_te", ""),
                            question_en=faq.get("question_en"),
                            answer_en=faq.get("answer_en"),
                        ))
                        faq_count += 1
            except Exception as e:
                logger.warning("Failed to seed FAQs", error=str(e))
            logger.info("Seeded FAQs", count=faq_count)

        # Load form templates
        template_count = 0
        if templates_file.exists():
            try:
                with open(templates_file, encoding="utf-8") as f:
                    templates = json.load(f)
                for tpl in templates:
                    session.add(FormTemplate(
                        name_te=tpl.get("name_te", ""),
                        name_en=tpl.get("name_en", ""),
                        department=tpl.get("department", "General"),
                        scheme_code=tpl.get("scheme_code"),
                        gsws_form_code=tpl.get("gsws_form_code"),
                        fields=tpl.get("fields", {}),
                        output_format=tpl.get("output_format", "pdf"),
                    ))
                    template_count += 1
            except Exception as e:
                logger.warning("Failed to seed templates", error=str(e))
            logger.info("Seeded form templates", count=template_count)

        await session.commit()
    logger.info("Database seeding complete")


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
    docs_url="/docs",      # Always enabled for demo/testing
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID middleware — must be added before rate limiter so all
# downstream log lines (including rate-limit hits) carry the request ID.
from app.core.correlation import CorrelationIdMiddleware
app.add_middleware(CorrelationIdMiddleware)

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
