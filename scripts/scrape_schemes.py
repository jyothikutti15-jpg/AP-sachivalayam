"""
Scrape AP government scheme data from public sources and structure into JSON.

Sources:
1. Navaratnalu official website
2. GSWS portal public pages
3. AP government GO repository

This script generates structured JSON scheme files that can be loaded
into the database via seed_db.py.
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx
import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = structlog.get_logger()

SCHEMES_DIR = Path(__file__).parent.parent / "app" / "data" / "schemes"

# Known AP government scheme information pages
SCHEME_SOURCES = [
    {
        "name": "AP Navaratnalu",
        "url": "https://navaratnalu.ap.gov.in",
        "type": "html",
    },
    {
        "name": "GSWS Schemes",
        "url": "https://gsws.ap.gov.in",
        "type": "html",
    },
]


async def scrape_page(url: str) -> str | None:
    """Fetch a web page and return its content."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers={
                "User-Agent": "AP-Sachivalayam-Copilot/1.0 (Government Scheme Research)"
            })
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.warning("Failed to fetch page", url=url, error=str(e))
        return None


def extract_scheme_data_from_html(html: str, source: str) -> list[dict]:
    """Extract scheme information from HTML content.

    This is a best-effort extractor. For production, you would use
    a more sophisticated parser tailored to each source site's structure.
    """
    # NOTE: In production, this would use BeautifulSoup to parse
    # the specific HTML structure of each government website.
    # For now, we rely on the manually curated JSON files.
    logger.info("HTML extraction is best-effort", source=source)
    return []


def generate_scheme_template(
    code: str,
    name_te: str,
    name_en: str,
    department: str,
) -> dict:
    """Generate a scheme JSON template for manual completion."""
    return {
        "scheme_code": code,
        "name_te": name_te,
        "name_en": name_en,
        "department": department,
        "description_te": "",
        "description_en": "",
        "eligibility_criteria": {},
        "required_documents": {"mandatory": []},
        "benefit_amount": "",
        "application_process_te": "",
        "go_reference": "",
        "effective_from": "",
        "is_active": True,
    }


def validate_scheme_file(filepath: Path) -> list[str]:
    """Validate a scheme JSON file for completeness."""
    errors = []
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    required_fields = [
        "scheme_code", "name_te", "name_en", "department",
        "eligibility_criteria", "benefit_amount",
    ]
    for field in required_fields:
        if not data.get(field):
            errors.append(f"Missing or empty: {field}")

    if not data.get("description_te") and not data.get("description_en"):
        errors.append("Must have at least one description (te or en)")

    if isinstance(data.get("eligibility_criteria"), dict) and not data["eligibility_criteria"]:
        errors.append("eligibility_criteria is empty")

    return errors


async def validate_all_schemes():
    """Validate all scheme JSON files."""
    print(f"\nValidating scheme files in {SCHEMES_DIR}...")
    total = 0
    errors_found = 0

    for filepath in sorted(SCHEMES_DIR.glob("*.json")):
        total += 1
        errors = validate_scheme_file(filepath)
        if errors:
            errors_found += 1
            print(f"  WARN {filepath.name}:")
            for err in errors:
                print(f"    - {err}")
        else:
            print(f"  OK   {filepath.name}")

    print(f"\n{total} files checked, {errors_found} with warnings")


async def scrape_and_update():
    """Main scraping pipeline."""
    print("AP Scheme Scraper")
    print("=" * 50)
    print(f"Scheme files directory: {SCHEMES_DIR}")
    print(f"Existing schemes: {len(list(SCHEMES_DIR.glob('*.json')))}")

    # Try to scrape from known sources
    for source in SCHEME_SOURCES:
        print(f"\nScraping: {source['name']} ({source['url']})")
        html = await scrape_page(source["url"])
        if html:
            schemes = extract_scheme_data_from_html(html, source["name"])
            print(f"  Extracted: {len(schemes)} schemes")
            for scheme in schemes:
                filename = scheme["scheme_code"].lower().replace("-", "_") + ".json"
                filepath = SCHEMES_DIR / filename
                if not filepath.exists():
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(scheme, f, ensure_ascii=False, indent=2)
                    print(f"  NEW: {filename}")
        else:
            print("  Could not reach source — using existing curated data")

    # Validate all files
    await validate_all_schemes()


if __name__ == "__main__":
    if "--validate" in sys.argv:
        asyncio.run(validate_all_schemes())
    else:
        asyncio.run(scrape_and_update())
