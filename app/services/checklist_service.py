"""
Document Checklist Generator — Given a citizen's profile, generates a
personalized checklist of documents needed across all eligible schemes.

Avoids repeat visits by consolidating common documents and highlighting
which documents are shared across schemes.
"""

import json
from collections import Counter

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheme import Scheme
from app.schemas.checklist import (
    CitizenProfile,
    DocumentChecklistResponse,
    DocumentItem,
    SchemeDocumentGroup,
)
from app.services.llm_service import LLMRouter

logger = structlog.get_logger()

CHECKLIST_SYSTEM_PROMPT = """You are an AP government scheme eligibility checker.
Given a citizen's profile and a list of schemes with their eligibility criteria,
determine which schemes the citizen is likely eligible for.

Respond in JSON format:
{{
    "eligible_schemes": [
        {{
            "scheme_code": "...",
            "is_eligible": true/false,
            "confidence": 0.0-1.0,
            "reason_te": "Telugu explanation"
        }}
    ]
}}

Be conservative — mark as eligible only when the citizen clearly meets the criteria.
If information is missing for a criterion, set confidence lower but still include the scheme
if the available data strongly suggests eligibility.

CITIZEN PROFILE:
{citizen_profile}

SCHEMES:
{schemes_data}
"""

# Common AP government documents with Telugu names
COMMON_DOCUMENTS = {
    "aadhaar_card": ("ఆధార్ కార్డు", "Aadhaar Card"),
    "ration_card": ("రేషన్ కార్డు", "Ration Card"),
    "income_certificate": ("ఆదాయ ధృవీకరణ పత్రం", "Income Certificate"),
    "caste_certificate": ("కులధృవీకరణ పత్రం", "Caste Certificate"),
    "residence_certificate": ("నివాస ధృవీకరణ పత్రం", "Residence Certificate"),
    "bank_passbook": ("బ్యాంకు పాస్‌బుక్", "Bank Passbook"),
    "passport_photo": ("పాస్‌పోర్ట్ సైజు ఫోటో", "Passport Size Photo"),
    "voter_id": ("ఓటరు గుర్తింపు కార్డు", "Voter ID Card"),
    "birth_certificate": ("జనన ధృవీకరణ పత్రం", "Birth Certificate"),
    "disability_certificate": ("వికలాంగ ధృవీకరణ పత్రం", "Disability Certificate"),
    "land_document": ("భూమి పత్రాలు / పట్టాదారు పాస్‌బుక్", "Land Document / Pattadar Passbook"),
    "school_certificate": ("పాఠశాల ధృవీకరణ పత్రం", "School Study Certificate"),
    "death_certificate": ("మరణ ధృవీకరణ పత్రం", "Death Certificate"),
    "marriage_certificate": ("వివాహ ధృవీకరణ పత్రం", "Marriage Certificate"),
    "medical_certificate": ("వైద్య ధృవీకరణ పత్రం", "Medical Certificate"),
}


class ChecklistService:
    """Generates personalized document checklists for citizens."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMRouter()

    async def generate_checklist(
        self, citizen: CitizenProfile
    ) -> DocumentChecklistResponse:
        """Generate a full document checklist for a citizen across all eligible schemes."""

        # 1. Fetch all active schemes
        result = await self.db.execute(
            select(Scheme).where(Scheme.is_active.is_(True))
        )
        schemes = list(result.scalars().all())

        if not schemes:
            return DocumentChecklistResponse(
                citizen_name=citizen.name,
                ai_summary_te="ప్రస్తుతం ఏ పథకాలు అందుబాటులో లేవు.",
            )

        # 2. Use LLM to determine eligibility across all schemes
        eligible_schemes = await self._check_eligibility_bulk(citizen, schemes)

        # 3. Build document lists per eligible scheme
        scheme_groups: list[SchemeDocumentGroup] = []
        all_docs: list[str] = []  # track all doc keys for dedup

        for scheme in schemes:
            match = next(
                (e for e in eligible_schemes if e["scheme_code"] == scheme.scheme_code),
                None,
            )
            if not match or not match.get("is_eligible", False):
                continue

            docs = self._extract_documents(scheme)
            all_docs.extend(docs)

            scheme_groups.append(
                SchemeDocumentGroup(
                    scheme_code=scheme.scheme_code,
                    scheme_name_te=scheme.name_te,
                    scheme_name_en=scheme.name_en,
                    is_eligible=True,
                    confidence=match.get("confidence", 0.0),
                    documents=docs,
                    eligibility_reason_te=match.get("reason_te", ""),
                )
            )

        # 4. Identify common documents (needed by 2+ schemes)
        doc_counts = Counter(all_docs)
        common_docs: list[DocumentItem] = []
        seen_common = set()

        for doc_key, count in doc_counts.most_common():
            if count >= 2 and doc_key not in seen_common:
                seen_common.add(doc_key)
                names = COMMON_DOCUMENTS.get(
                    doc_key, (doc_key, doc_key)
                )
                schemes_needing = [
                    sg.scheme_code
                    for sg in scheme_groups
                    if doc_key in sg.documents
                ]
                common_docs.append(
                    DocumentItem(
                        document_name_te=names[0],
                        document_name_en=names[1],
                        is_common=True,
                        required_for_schemes=schemes_needing,
                        notes_te=f"{count} పథకాలకు అవసరం",
                    )
                )

        unique_docs = len(set(all_docs))

        # 5. Generate Telugu summary
        summary = self._build_summary(citizen, scheme_groups, unique_docs)

        logger.info(
            "Checklist generated",
            citizen_name=citizen.name,
            eligible_schemes=len(scheme_groups),
            unique_documents=unique_docs,
        )

        return DocumentChecklistResponse(
            citizen_name=citizen.name,
            total_eligible_schemes=len(scheme_groups),
            common_documents=common_docs,
            scheme_documents=scheme_groups,
            total_unique_documents=unique_docs,
            ai_summary_te=summary,
        )

    async def _check_eligibility_bulk(
        self, citizen: CitizenProfile, schemes: list[Scheme]
    ) -> list[dict]:
        """Use LLM to check eligibility across all schemes at once."""
        citizen_data = citizen.model_dump(exclude_none=True)

        schemes_data = []
        for s in schemes:
            schemes_data.append({
                "scheme_code": s.scheme_code,
                "name_te": s.name_te,
                "name_en": s.name_en,
                "eligibility_criteria": s.eligibility_criteria,
            })

        prompt = "Determine which schemes this citizen is eligible for. Respond in JSON only."
        system_prompt = CHECKLIST_SYSTEM_PROMPT.format(
            citizen_profile=json.dumps(citizen_data, ensure_ascii=False),
            schemes_data=json.dumps(schemes_data, ensure_ascii=False),
        )

        try:
            response = await self.llm.call_claude_structured(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=3000,
            )
            data = json.loads(response)
            return data.get("eligible_schemes", [])
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Bulk eligibility check failed", error=str(e))
            # Fallback: rule-based matching
            return self._rule_based_eligibility(citizen, schemes)

    def _rule_based_eligibility(
        self, citizen: CitizenProfile, schemes: list[Scheme]
    ) -> list[dict]:
        """Fallback rule-based eligibility when LLM is unavailable."""
        results = []
        for scheme in schemes:
            criteria = scheme.eligibility_criteria or {}
            eligible = True
            confidence = 0.5

            # Check age
            if citizen.age and "min_age" in criteria:
                if citizen.age < criteria["min_age"]:
                    eligible = False
            if citizen.age and "max_age" in criteria:
                if citizen.age > criteria["max_age"]:
                    eligible = False

            # Check income
            if citizen.income and "max_income" in criteria:
                if citizen.income > criteria["max_income"]:
                    eligible = False

            # Check ration card
            if "ration_card" in criteria and citizen.ration_card:
                valid_cards = criteria["ration_card"]
                if isinstance(valid_cards, list) and citizen.ration_card not in valid_cards:
                    eligible = False

            if eligible:
                results.append({
                    "scheme_code": scheme.scheme_code,
                    "is_eligible": True,
                    "confidence": confidence,
                    "reason_te": "నియమ ఆధారిత తనిఖీ ద్వారా అర్హత నిర్ధారణ",
                })

        return results

    def _extract_documents(self, scheme: Scheme) -> list[str]:
        """Extract required document keys from a scheme's data."""
        docs = []
        required = scheme.required_documents
        if not required:
            return ["aadhaar_card", "bank_passbook"]

        if isinstance(required, list):
            for doc in required:
                if isinstance(doc, str):
                    key = self._normalize_doc_key(doc)
                    docs.append(key)
                elif isinstance(doc, dict):
                    key = self._normalize_doc_key(doc.get("name", doc.get("document", "")))
                    docs.append(key)
        elif isinstance(required, dict):
            for key, val in required.items():
                docs.append(self._normalize_doc_key(key))

        return docs or ["aadhaar_card", "bank_passbook"]

    def _normalize_doc_key(self, doc_name: str) -> str:
        """Normalize a document name to a standard key."""
        name_lower = doc_name.lower().strip()
        mappings = {
            "aadhaar": "aadhaar_card",
            "aadhar": "aadhaar_card",
            "ration": "ration_card",
            "income": "income_certificate",
            "caste": "caste_certificate",
            "residence": "residence_certificate",
            "bank": "bank_passbook",
            "photo": "passport_photo",
            "voter": "voter_id",
            "birth": "birth_certificate",
            "disability": "disability_certificate",
            "land": "land_document",
            "pattadar": "land_document",
            "school": "school_certificate",
            "study": "school_certificate",
            "death": "death_certificate",
            "marriage": "marriage_certificate",
            "medical": "medical_certificate",
        }
        for keyword, key in mappings.items():
            if keyword in name_lower:
                return key
        # Return cleaned version if no match
        return name_lower.replace(" ", "_").replace("-", "_")

    def _build_summary(
        self,
        citizen: CitizenProfile,
        scheme_groups: list[SchemeDocumentGroup],
        unique_docs: int,
    ) -> str:
        """Build a Telugu summary of the checklist."""
        if not scheme_groups:
            return "ఈ పౌరుడికి ప్రస్తుతం ఏ పథకాలకు అర్హత కనుగొనబడలేదు."

        scheme_names = ", ".join(sg.scheme_name_te for sg in scheme_groups[:5])
        more = f" మరియు {len(scheme_groups) - 5} ఇతర పథకాలు" if len(scheme_groups) > 5 else ""

        return (
            f"మొత్తం {len(scheme_groups)} పథకాలకు అర్హత ఉంది: {scheme_names}{more}. "
            f"మొత్తం {unique_docs} రకాల పత్రాలు అవసరం. "
            f"ఆధార్ కార్డు, రేషన్ కార్డు వంటి ఉమ్మడి పత్రాలు ఒకసారి తీసుకురావడం సరిపోతుంది."
        )
