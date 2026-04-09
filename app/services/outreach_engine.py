"""Outreach Engine — Rule-based matching of beneficiaries to schemes."""
import json
from datetime import datetime, timezone
from pathlib import Path

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beneficiary import Beneficiary
from app.models.outreach import OutreachRecord

logger = structlog.get_logger()

SCHEMES_DIR = Path(__file__).parent.parent / "data" / "schemes"


def _load_active_schemes() -> list[dict]:
    """Load all active scheme JSON files."""
    schemes = []
    for f in SCHEMES_DIR.glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)
        if data.get("is_active"):
            schemes.append(data)
    return schemes


class OutreachEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    def check_eligibility_rules(self, beneficiary: Beneficiary, scheme: dict) -> tuple[bool, float, str]:
        """Rule-based eligibility check. Returns (eligible, score, reasoning)."""
        ec = scheme.get("eligibility_criteria", {})
        excluded = ec.get("excluded", [])
        reasons = []
        score = 0.5  # Start neutral

        # Universal exclusions
        if beneficiary.is_govt_employee:
            for exc in excluded:
                if "government" in exc.lower() or "govt" in exc.lower():
                    return False, 0.0, "Government employee — excluded"

        if beneficiary.is_income_tax_payer:
            for exc in excluded:
                if "income tax" in exc.lower() or "tax" in exc.lower():
                    return False, 0.0, "Income tax payer — excluded"

        if beneficiary.owns_four_wheeler:
            for exc in excluded:
                if "four-wheeler" in exc.lower() or "four wheeler" in exc.lower():
                    return False, 0.0, "Four-wheeler owner — excluded"

        # Age checks
        if beneficiary.age:
            age_str = str(ec.get("age", ec.get("old_age_pension", {}).get("age", "")))
            if "60" in age_str and beneficiary.age >= 60:
                score += 0.2
                reasons.append("Age criterion met")
            elif "18" in age_str and beneficiary.age >= 18:
                score += 0.1
                reasons.append("Age criterion met")

        # Income checks
        if beneficiary.annual_income is not None:
            income_str = str(ec.get("income", ec.get("universal_criteria", {}).get("income", "")))
            if "10,000" in income_str and beneficiary.annual_income <= 120000:
                score += 0.2
                reasons.append("Income criterion met")
            elif "2,50,000" in income_str and beneficiary.annual_income <= 250000:
                score += 0.15
                reasons.append("Income criterion met")
            elif "5,00,000" in income_str and beneficiary.annual_income <= 500000:
                score += 0.1
                reasons.append("Income criterion met")

        # Ration card checks
        if beneficiary.ration_card_type:
            rc_str = str(ec.get("ration_card", ec.get("bpl_status", "")))
            if beneficiary.ration_card_type.lower() in ("white", "rice", "antyodaya"):
                if "white" in rc_str.lower() or "rice" in rc_str.lower() or "bpl" in rc_str.lower():
                    score += 0.2
                    reasons.append("Ration card criterion met")

        # Caste checks
        if beneficiary.caste_category:
            caste_str = str(ec.get("caste", ""))
            if beneficiary.caste_category.upper() in caste_str.upper():
                score += 0.1
                reasons.append("Caste category matches")

        # Disability checks
        if beneficiary.is_disabled and beneficiary.disability_percentage:
            if "disabled" in str(ec).lower() or "disability" in str(ec).lower():
                score += 0.3
                reasons.append("Disability criterion applicable")

        # Occupation checks
        if beneficiary.occupation:
            occ_str = str(ec.get("occupation", ""))
            if beneficiary.occupation.lower() in occ_str.lower():
                score += 0.2
                reasons.append("Occupation matches")

        score = min(score, 1.0)
        eligible = score >= 0.5  # Threshold for recommendation

        reasoning = "; ".join(reasons) if reasons else "General eligibility potential"
        return eligible, round(score, 2), reasoning

    async def scan_secretariat(self, secretariat_id: int) -> list[dict]:
        """Scan all beneficiaries in a secretariat against all active schemes."""
        # Get beneficiaries
        result = await self.db.execute(
            select(Beneficiary).where(
                and_(
                    Beneficiary.secretariat_id == secretariat_id,
                    Beneficiary.opt_out == False,
                    Beneficiary.is_govt_employee == False,
                )
            )
        )
        beneficiaries = result.scalars().all()

        # Get active schemes
        schemes = _load_active_schemes()

        # Get existing outreach records to avoid duplicates
        existing = await self.db.execute(
            select(OutreachRecord.beneficiary_id, OutreachRecord.scheme_code).where(
                OutreachRecord.secretariat_id == secretariat_id
            )
        )
        existing_pairs = {(r.beneficiary_id, r.scheme_code) for r in existing.all()}

        matches = []
        for ben in beneficiaries:
            enrolled = set(ben.schemes_enrolled or [])
            for scheme in schemes:
                code = scheme["scheme_code"]
                # Skip if already enrolled or already identified
                if code in enrolled or (ben.id, code) in existing_pairs:
                    continue

                eligible, score, reasoning = self.check_eligibility_rules(ben, scheme)
                if eligible:
                    record = OutreachRecord(
                        beneficiary_id=ben.id,
                        scheme_code=code,
                        secretariat_id=secretariat_id,
                        match_score=score,
                        match_reasoning_te=reasoning,
                        status="identified",
                    )
                    self.db.add(record)
                    matches.append({
                        "beneficiary_id": ben.id,
                        "beneficiary_name": ben.name_te,
                        "scheme_code": code,
                        "scheme_name": scheme["name_te"],
                        "match_score": score,
                        "reasoning": reasoning,
                    })

        if matches:
            await self.db.flush()

        logger.info("Outreach scan complete", secretariat_id=secretariat_id,
                    beneficiaries=len(beneficiaries), matches=len(matches))
        return matches

    async def scan_beneficiary(self, beneficiary_id: int) -> list[dict]:
        """Find all schemes a single beneficiary might be eligible for."""
        result = await self.db.execute(
            select(Beneficiary).where(Beneficiary.id == beneficiary_id)
        )
        ben = result.scalar_one_or_none()
        if not ben:
            return []

        schemes = _load_active_schemes()
        enrolled = set(ben.schemes_enrolled or [])
        matches = []

        for scheme in schemes:
            code = scheme["scheme_code"]
            if code in enrolled:
                continue
            eligible, score, reasoning = self.check_eligibility_rules(ben, scheme)
            if eligible:
                matches.append({
                    "scheme_code": code,
                    "scheme_name": scheme["name_te"],
                    "benefit_amount": scheme.get("benefit_amount", ""),
                    "match_score": score,
                    "reasoning": reasoning,
                })

        matches.sort(key=lambda m: m["match_score"], reverse=True)
        return matches

    async def get_pending_outreach(self, secretariat_id: int) -> list:
        """Get pending outreach records for a secretariat (for conversation handler)."""
        result = await self.db.execute(
            select(OutreachRecord)
            .join(Beneficiary, OutreachRecord.beneficiary_id == Beneficiary.id)
            .where(
                OutreachRecord.secretariat_id == secretariat_id,
                OutreachRecord.status == "identified",
            )
            .order_by(OutreachRecord.match_score.desc())
            .limit(20)
        )
        records = result.scalars().all()

        # Attach beneficiary names for display
        for record in records:
            ben_result = await self.db.execute(
                select(Beneficiary.name_te).where(Beneficiary.id == record.beneficiary_id)
            )
            ben_name = ben_result.scalar_one_or_none()
            record.beneficiary_name = ben_name or "Unknown"
            record.eligibility_score = record.match_score

        return records

    async def get_outreach_list(
        self, secretariat_id: int, scheme_code: str | None = None,
        status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict], int]:
        """Get existing outreach records for a secretariat."""
        query = select(OutreachRecord).where(
            OutreachRecord.secretariat_id == secretariat_id
        )
        if scheme_code:
            query = query.where(OutreachRecord.scheme_code == scheme_code)
        if status:
            query = query.where(OutreachRecord.status == status)

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        query = query.order_by(OutreachRecord.match_score.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        records = result.scalars().all()

        items = []
        for r in records:
            # Get beneficiary name
            ben_result = await self.db.execute(
                select(Beneficiary.name_te, Beneficiary.phone_number).where(Beneficiary.id == r.beneficiary_id)
            )
            ben = ben_result.one_or_none()
            items.append({
                "id": str(r.id),
                "beneficiary_id": r.beneficiary_id,
                "beneficiary_name": ben.name_te if ben else "Unknown",
                "beneficiary_phone": ben.phone_number if ben else None,
                "scheme_code": r.scheme_code,
                "match_score": r.match_score,
                "reasoning": r.match_reasoning_te,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return items, total

    async def mark_notified(self, outreach_id) -> dict | None:
        """Mark an outreach record as notified."""
        import uuid as uuid_mod
        if isinstance(outreach_id, str):
            outreach_id = uuid_mod.UUID(outreach_id)
        result = await self.db.execute(
            select(OutreachRecord).where(OutreachRecord.id == outreach_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None
        record.status = "notified"
        record.notified_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"id": str(record.id), "status": "notified"}

    async def mark_applied(self, outreach_id) -> dict | None:
        """Mark an outreach record as applied."""
        import uuid as uuid_mod
        if isinstance(outreach_id, str):
            outreach_id = uuid_mod.UUID(outreach_id)
        result = await self.db.execute(
            select(OutreachRecord).where(OutreachRecord.id == outreach_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None
        record.status = "applied"
        record.applied_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"id": str(record.id), "status": "applied"}
