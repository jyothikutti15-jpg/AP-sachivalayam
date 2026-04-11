from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

# Database engine and session.
# For Neon/Supabase/other hosted Postgres, SSL is required. asyncpg uses
# ssl=True via connect_args (not via URL query params like psycopg2).
_db_url = settings.async_database_url
_connect_args: dict = {}
if any(host in _db_url for host in ("neon.tech", "supabase.co", "render.com", "amazonaws.com")):
    _connect_args["ssl"] = True

engine = create_async_engine(
    _db_url,
    echo=settings.database_echo,
    pool_size=20,
    max_overflow=10,
    connect_args=_connect_args,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
AsyncSessionLocal = async_session_factory  # Alias for workers

# Redis client
redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> aioredis.Redis:
    return redis_client
