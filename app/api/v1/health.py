from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis

router = APIRouter()


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
):
    checks = {"status": "healthy", "services": {}}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["services"]["database"] = "ok"
    except Exception as e:
        checks["services"]["database"] = f"error: {e}"
        checks["status"] = "degraded"

    # Redis check
    try:
        redis = await get_redis()
        await redis.ping()
        checks["services"]["redis"] = "ok"
    except Exception as e:
        checks["services"]["redis"] = f"error: {e}"
        checks["status"] = "degraded"

    return checks
