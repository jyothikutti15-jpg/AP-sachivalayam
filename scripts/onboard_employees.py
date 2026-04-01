"""Bulk onboard employees from CSV file.

CSV format: phone_number,name_te,name_en,designation,department,secretariat_gsws_code
"""
import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from sqlalchemy import select

from app.dependencies import async_session_factory, engine
from app.models import Base, Employee, Secretariat


async def onboard(csv_path: str):
    """Onboard employees from CSV."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} employees to onboard")

    async with async_session_factory() as session:
        added = 0
        skipped = 0

        for row in rows:
            phone = row["phone_number"].strip()

            existing = await session.execute(
                select(Employee).where(Employee.phone_number == phone)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            # Look up secretariat
            sec_id = None
            if row.get("secretariat_gsws_code"):
                sec_result = await session.execute(
                    select(Secretariat).where(
                        Secretariat.gsws_code == row["secretariat_gsws_code"].strip()
                    )
                )
                sec = sec_result.scalar_one_or_none()
                if sec:
                    sec_id = sec.id

            employee = Employee(
                phone_number=phone,
                name_te=row.get("name_te", "").strip(),
                name_en=row.get("name_en", "").strip(),
                designation=row.get("designation", "Unknown").strip(),
                department=row.get("department", "Unknown").strip(),
                secretariat_id=sec_id,
                onboarded_at=datetime.now(timezone.utc),
                is_active=True,
            )
            session.add(employee)
            added += 1

        await session.commit()
        print(f"Added: {added}, Skipped (existing): {skipped}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/onboard_employees.py --csv employees.csv")
        print("\nCSV format: phone_number,name_te,name_en,designation,department,secretariat_gsws_code")
        sys.exit(1)

    csv_path = sys.argv[-1]
    asyncio.run(onboard(csv_path))
