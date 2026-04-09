#!/bin/bash
# Render start script — runs migrations and seeds on first deploy, then starts the app.

set -e

echo "=== AP Sachivalayam AI Copilot — Starting ==="

# Run database migrations
echo "Running database migrations..."
python -c "
from app.dependencies import engine
from app.models import Base
import asyncio

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Database tables created/verified.')

asyncio.run(init_db())
"

# Seed data (schemes, FAQs, templates) — idempotent
echo "Seeding data..."
python scripts/seed_db.py || echo "Seed script not critical, continuing..."

# Start the application
echo "Starting uvicorn on port ${PORT:-10000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
