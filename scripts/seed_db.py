"""Seed the database with initial scheme data, FAQs, and sample secretariats."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.dependencies import async_session_factory, engine
from app.models import Base, Scheme, SchemeFAQ, Secretariat


SCHEMES_DIR = Path(__file__).parent.parent / "app" / "data" / "schemes"
FAQS_FILE = Path(__file__).parent.parent / "app" / "data" / "scheme_faqs.json"

# Sample secretariats for pilot (5 secretariats across 3 districts)
PILOT_SECRETARIATS = [
    {"gsws_code": "13-01-0001", "name_te": "విజయవాడ సచివాలయం 1", "name_en": "Vijayawada Secretariat 1", "mandal": "Vijayawada Urban", "district": "NTR", "pin_code": "520001"},
    {"gsws_code": "13-01-0002", "name_te": "విజయవాడ సచివాలయం 2", "name_en": "Vijayawada Secretariat 2", "mandal": "Vijayawada Rural", "district": "NTR", "pin_code": "520002"},
    {"gsws_code": "07-03-0015", "name_te": "తిరుపతి సచివాలయం 1", "name_en": "Tirupati Secretariat 1", "mandal": "Tirupati Urban", "district": "Tirupati", "pin_code": "517501"},
    {"gsws_code": "01-05-0023", "name_te": "శ్రీకాకుళం సచివాలయం 1", "name_en": "Srikakulam Secretariat 1", "mandal": "Srikakulam", "district": "Srikakulam", "pin_code": "532001", "connectivity_tier": "low"},
    {"gsws_code": "01-05-0024", "name_te": "నరసన్నపేట సచివాలయం", "name_en": "Narasannapeta Secretariat", "mandal": "Narasannapeta", "district": "Srikakulam", "pin_code": "532003", "connectivity_tier": "low"},
]

def load_all_faqs() -> dict:
    """Load all FAQs from the centralized JSON file."""
    if FAQS_FILE.exists():
        with open(FAQS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


async def seed():
    """Run the database seeding."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Seed secretariats
        for sec_data in PILOT_SECRETARIATS:
            existing = await session.execute(
                select(Secretariat).where(Secretariat.gsws_code == sec_data["gsws_code"])
            )
            if not existing.scalar_one_or_none():
                session.add(Secretariat(**sec_data))
                print(f"  Added secretariat: {sec_data['name_en']}")

        # Load all FAQs
        all_faqs = load_all_faqs()
        total_faqs = 0

        # Seed schemes from JSON files
        for scheme_file in sorted(SCHEMES_DIR.glob("*.json")):
            with open(scheme_file, encoding="utf-8") as f:
                data = json.load(f)

            existing = await session.execute(
                select(Scheme).where(Scheme.scheme_code == data["scheme_code"])
            )
            if not existing.scalar_one_or_none():
                scheme = Scheme(
                    scheme_code=data["scheme_code"],
                    name_te=data["name_te"],
                    name_en=data["name_en"],
                    department=data["department"],
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
                await session.flush()
                print(f"  Added scheme: {data['name_en']}")

                # Add FAQs for this scheme from centralized FAQ file
                scheme_faqs = all_faqs.get(data["scheme_code"], [])
                for faq_data in scheme_faqs:
                    faq = SchemeFAQ(scheme_id=scheme.id, **faq_data)
                    session.add(faq)
                    total_faqs += 1

        await session.commit()
        print(f"\n  Total FAQs loaded: {total_faqs}")

        # Seed form templates
        print("\nLoading form templates...")
        from app.services.form_filler import FormFiller
        templates_loaded = await FormFiller.load_templates_to_db(session)
        await session.commit()
        print(f"  Form templates loaded: {templates_loaded}")

        print("\nDatabase seeded successfully!")


if __name__ == "__main__":
    print("Seeding AP Sachivalayam database...")
    asyncio.run(seed())
