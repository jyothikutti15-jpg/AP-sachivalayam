"""
Form Filler — Auto-fills government forms from voice/text descriptions.

Flow: Employee describes citizen → Claude extracts fields → Validate → Draft → Confirm → PDF → GSWS
"""
import json
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_aadhaar, mask_aadhaar
from app.models.form import FormSubmission, FormTemplate
from app.schemas.form import AutoFillResponse
from app.services.llm_service import LLMRouter

logger = structlog.get_logger()

TEMPLATES_FILE = Path(__file__).parent.parent / "data" / "templates" / "form_templates.json"

FORM_EXTRACTION_SYSTEM = """You are a precise data extraction assistant for AP government forms.

Extract citizen details from the employee's description (Telugu or English).
Map extracted values to the form fields listed below.

## Form Fields:
{fields_description}

## Rules:
- Convert Telugu numbers: రెండు లక్షలు → 200000, ముప్పై ఐదు → 35
- For Aadhaar: extract ONLY last 4 digits. Replace rest with XXXX XXXX.
- For names: keep Telugu script if input is Telugu
- For income: convert to annual if given monthly (multiply by 12)
- For select fields: match to closest valid option
- Confidence: 1.0 = explicitly stated, 0.7 = inferred, 0.3 = guessed
- If a required field is missing, list it in missing_fields

## Return ONLY valid JSON:
{{
    "field_values": {{"field_name": "value", ...}},
    "confidence_scores": {{"field_name": 0.0-1.0, ...}},
    "missing_fields": ["field_name", ...]
}}"""


class FormFiller:
    """Auto-fills government forms from voice/text descriptions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMRouter()

    async def auto_fill(
        self,
        template_id: int,
        employee_id: int,
        input_text: str,
        citizen_name: str | None = None,
        voice_entities: dict | None = None,
    ) -> AutoFillResponse:
        """Extract form fields from text and create a draft submission."""
        # 1. Get form template
        result = await self.db.execute(
            select(FormTemplate).where(FormTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            return AutoFillResponse(
                submission_id=uuid.uuid4(),
                extracted_fields={},
                status="error",
                message_te="ఫారం template కనుగొనబడలేదు.",
            )

        # 2. Build field descriptions for Claude
        fields_desc = self._build_fields_description(template.fields)

        # 3. Enhance input with voice entities if available
        enhanced_input = input_text
        if voice_entities:
            entity_text = self._entities_to_text(voice_entities)
            enhanced_input = f"{input_text}\n\nExtracted entities: {entity_text}"

        # 4. Extract fields using Claude
        prompt = f"Employee's description of citizen:\n\n{enhanced_input}"
        system = FORM_EXTRACTION_SYSTEM.format(fields_description=fields_desc)

        response = await self.llm.call_claude_structured(
            prompt=prompt,
            system_prompt=system,
        )

        # 5. Parse extraction result
        field_values, confidence_scores, missing_fields = self._parse_extraction(
            response, template.fields
        )

        # 6. Override citizen name if provided
        name_field = self._find_name_field(template.fields)
        if citizen_name and name_field:
            field_values[name_field] = citizen_name
            confidence_scores[name_field] = 1.0

        # 7. Apply voice entities as fallback
        if voice_entities:
            field_values, confidence_scores = self._apply_voice_entities(
                field_values, confidence_scores, voice_entities, template.fields
            )

        # 8. Secure Aadhaar handling
        aadhaar_hash = None
        for field_name, field_def in template.fields.items():
            if isinstance(field_def, dict) and field_def.get("type") == "aadhaar_last4":
                if field_name in field_values:
                    raw = str(field_values[field_name])
                    # Only keep last 4 digits
                    digits = "".join(c for c in raw if c.isdigit())
                    if len(digits) >= 4:
                        field_values[field_name] = digits[-4:]
                    if len(digits) >= 12:
                        aadhaar_hash = hash_aadhaar(digits)

        # 9. Create draft submission
        submission = FormSubmission(
            template_id=template_id,
            employee_id=employee_id,
            citizen_name=citizen_name or field_values.get(name_field or "applicant_name"),
            citizen_aadhaar_hash=aadhaar_hash,
            field_values=field_values,
            status="draft",
        )
        self.db.add(submission)
        await self.db.flush()

        # 10. Build confirmation message
        message_te = self._build_confirmation_message(
            template, field_values, confidence_scores, missing_fields
        )

        logger.info(
            "Form auto-filled",
            template=template.name_en,
            fields_extracted=len(field_values),
            missing=len(missing_fields),
            submission_id=str(submission.id),
        )

        return AutoFillResponse(
            submission_id=submission.id,
            extracted_fields=field_values,
            confidence_scores=confidence_scores,
            status="draft",
            message_te=message_te,
        )

    async def auto_fill_by_scheme(
        self,
        scheme_code: str,
        employee_id: int,
        input_text: str,
        voice_entities: dict | None = None,
    ) -> AutoFillResponse:
        """Find the template for a scheme and auto-fill it."""
        result = await self.db.execute(
            select(FormTemplate).where(FormTemplate.scheme_id.isnot(None))
        )
        templates = result.scalars().all()

        # Find template matching the scheme
        from app.models.scheme import Scheme
        scheme_result = await self.db.execute(
            select(Scheme).where(Scheme.scheme_code == scheme_code)
        )
        scheme = scheme_result.scalar_one_or_none()

        if scheme:
            for t in templates:
                if t.scheme_id == scheme.id:
                    return await self.auto_fill(
                        t.id, employee_id, input_text, voice_entities=voice_entities
                    )

        return AutoFillResponse(
            submission_id=uuid.uuid4(),
            extracted_fields={},
            status="error",
            message_te=f"'{scheme_code}' పథకానికి form template లేదు.",
        )

    def _build_fields_description(self, fields: dict) -> str:
        """Build human-readable field descriptions for Claude."""
        lines = []
        for name, defn in fields.items():
            if isinstance(defn, dict):
                label = defn.get("label_te", defn.get("label_en", name))
                ftype = defn.get("type", "text")
                required = "REQUIRED" if defn.get("required") else "optional"
                options = defn.get("options", [])
                opt_str = f" (options: {', '.join(str(o) for o in options)})" if options else ""
                lines.append(f"- {name}: {label} [{ftype}] {required}{opt_str}")
            else:
                lines.append(f"- {name}: {defn}")
        return "\n".join(lines)

    def _parse_extraction(
        self, response: str, template_fields: dict
    ) -> tuple[dict, dict, list]:
        """Parse Claude's JSON extraction response."""
        try:
            # Handle potential markdown code blocks
            text = response.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            return (
                data.get("field_values", {}),
                data.get("confidence_scores", {}),
                data.get("missing_fields", []),
            )
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse form extraction", response=response[:200])
            # Return all required fields as missing
            missing = [
                name for name, defn in template_fields.items()
                if isinstance(defn, dict) and defn.get("required")
            ]
            return {}, {}, missing

    def _find_name_field(self, fields: dict) -> str | None:
        """Find the primary name field in a template."""
        name_candidates = [
            "applicant_name", "citizen_name", "mother_name", "farmer_name",
            "patient_name", "student_name", "bride_name", "deceased_name",
            "nominee_name",
        ]
        for candidate in name_candidates:
            if candidate in fields:
                return candidate
        return None

    def _entities_to_text(self, entities: dict) -> str:
        """Convert voice entities dict to text for Claude context."""
        parts = []
        if "names" in entities:
            parts.append(f"Names: {', '.join(entities['names'])}")
        if "age" in entities:
            parts.append(f"Age: {entities['age']}")
        if "income" in entities:
            parts.append(f"Income: ₹{entities['income']}")
        if "ration_card" in entities:
            parts.append(f"Ration card: {entities['ration_card']}")
        if "caste" in entities:
            parts.append(f"Caste: {entities['caste']}")
        if "scheme" in entities:
            parts.append(f"Scheme: {entities['scheme']}")
        return "; ".join(parts)

    def _apply_voice_entities(
        self,
        field_values: dict,
        confidence_scores: dict,
        entities: dict,
        template_fields: dict,
    ) -> tuple[dict, dict]:
        """Fill in missing fields from voice entity extraction."""
        # Map entities to common field names
        entity_field_map = {
            "age": ["age", "patient_age", "bride_age", "groom_age", "deceased_age"],
            "income": ["annual_income"],
            "ration_card": ["ration_card_type"],
            "caste": ["caste"],
        }

        for entity_key, field_names in entity_field_map.items():
            if entity_key in entities:
                for field_name in field_names:
                    if field_name in template_fields and field_name not in field_values:
                        field_values[field_name] = entities[entity_key]
                        confidence_scores[field_name] = 0.7

        # Names
        if "names" in entities and entities["names"]:
            name_field = self._find_name_field(template_fields)
            if name_field and name_field not in field_values:
                field_values[name_field] = entities["names"][0]
                confidence_scores[name_field] = 0.7

        return field_values, confidence_scores

    def _build_confirmation_message(
        self,
        template: FormTemplate,
        field_values: dict,
        confidence_scores: dict,
        missing_fields: list,
    ) -> str:
        """Build a Telugu confirmation message for WhatsApp."""
        lines = [f"📝 *{template.name_te}* — Auto-fill complete\n"]

        # Show extracted fields
        for field_name, value in field_values.items():
            defn = template.fields.get(field_name, {})
            label = defn.get("label_te", field_name) if isinstance(defn, dict) else field_name
            conf = confidence_scores.get(field_name, 0.5)
            conf_icon = "✅" if conf >= 0.8 else "⚠️" if conf >= 0.5 else "❓"
            lines.append(f"{conf_icon} {label}: {value}")

        # Show missing fields
        if missing_fields:
            lines.append("\n❌ *ఈ details లభించలేదు:*")
            for field_name in missing_fields:
                defn = template.fields.get(field_name, {})
                label = defn.get("label_te", field_name) if isinstance(defn, dict) else field_name
                lines.append(f"  • {label}")

        # Action prompt
        if missing_fields:
            lines.append("\nMissing details text లో పంపండి లేదా 'cancel' చేయండి.")
        else:
            lines.append("\n✅ అన్ని details filled. PDF generate చేయాలా?")

        return "\n".join(lines)

    @staticmethod
    async def load_templates_to_db(db: AsyncSession) -> int:
        """Load form templates from JSON file into database. Called during seeding."""
        if not TEMPLATES_FILE.exists():
            return 0

        with open(TEMPLATES_FILE, encoding="utf-8") as f:
            templates_data = json.load(f)

        from app.models.scheme import Scheme

        loaded = 0
        for data in templates_data:
            # Check if template already exists
            existing = await db.execute(
                select(FormTemplate).where(
                    FormTemplate.gsws_form_code == data.get("gsws_form_code")
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Find scheme ID
            scheme_id = None
            if data.get("scheme_code"):
                scheme_result = await db.execute(
                    select(Scheme).where(Scheme.scheme_code == data["scheme_code"])
                )
                scheme = scheme_result.scalar_one_or_none()
                if scheme:
                    scheme_id = scheme.id

            template = FormTemplate(
                name_te=data["name_te"],
                name_en=data["name_en"],
                department=data.get("department"),
                scheme_id=scheme_id,
                fields=data["fields"],
                output_format=data.get("output_format", "pdf"),
                gsws_form_code=data.get("gsws_form_code"),
            )
            db.add(template)
            loaded += 1

        await db.flush()
        return loaded
