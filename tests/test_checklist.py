"""Tests for Document Checklist Generator (Feature 8)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.checklist import CitizenProfile, DocumentChecklistResponse
from app.services.checklist_service import ChecklistService, COMMON_DOCUMENTS


# --- Unit Tests for ChecklistService ---

class TestChecklistService:
    """Tests for the document checklist service."""

    def _make_mock_scheme(self, code, name_te, name_en, criteria=None, docs=None):
        scheme = MagicMock()
        scheme.scheme_code = code
        scheme.name_te = name_te
        scheme.name_en = name_en
        scheme.is_active = True
        scheme.eligibility_criteria = criteria or {}
        scheme.required_documents = docs or ["aadhaar_card", "bank_passbook"]
        return scheme

    @pytest.mark.asyncio
    async def test_generate_checklist_basic(self):
        """Test basic checklist generation with eligible schemes."""
        db = AsyncMock()
        schemes = [
            self._make_mock_scheme(
                "ysr_amma_vodi", "వైఎస్సార్ అమ్మ ఒడి", "YSR Amma Vodi",
                {"max_income": 250000, "min_age": 18},
                ["aadhaar_card", "ration_card", "income_certificate", "school_certificate"],
            ),
            self._make_mock_scheme(
                "ysr_cheyutha", "వైఎస్సార్ చేయూత", "YSR Cheyutha",
                {"min_age": 45, "max_age": 60, "max_income": 250000},
                ["aadhaar_card", "ration_card", "bank_passbook", "caste_certificate"],
            ),
        ]

        # Mock DB to return schemes
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = schemes
        db.execute = AsyncMock(return_value=mock_result)

        service = ChecklistService(db=db)

        # Mock LLM call
        with patch.object(service, '_check_eligibility_bulk', return_value=[
            {"scheme_code": "ysr_amma_vodi", "is_eligible": True, "confidence": 0.9, "reason_te": "అర్హత ఉంది"},
            {"scheme_code": "ysr_cheyutha", "is_eligible": True, "confidence": 0.85, "reason_te": "అర్హత ఉంది"},
        ]):
            citizen = CitizenProfile(
                name="రామ్మూర్తి",
                age=50,
                income=150000,
                caste="BC",
                ration_card="white",
                has_school_children=True,
            )
            result = await service.generate_checklist(citizen)

        assert isinstance(result, DocumentChecklistResponse)
        assert result.total_eligible_schemes == 2
        assert result.total_unique_documents > 0
        assert len(result.common_documents) > 0  # aadhaar & ration card are common
        assert result.citizen_name == "రామ్మూర్తి"

    @pytest.mark.asyncio
    async def test_generate_checklist_no_eligible_schemes(self):
        """Test checklist when no schemes match."""
        db = AsyncMock()
        schemes = [
            self._make_mock_scheme("ysr_amma_vodi", "అమ్మ ఒడి", "Amma Vodi"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = schemes
        db.execute = AsyncMock(return_value=mock_result)

        service = ChecklistService(db=db)

        with patch.object(service, '_check_eligibility_bulk', return_value=[]):
            citizen = CitizenProfile(name="Test", age=25, income=500000)
            result = await service.generate_checklist(citizen)

        assert result.total_eligible_schemes == 0
        assert len(result.scheme_documents) == 0

    @pytest.mark.asyncio
    async def test_generate_checklist_no_schemes_in_db(self):
        """Test checklist when no active schemes exist."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        service = ChecklistService(db=db)
        citizen = CitizenProfile(name="Test")
        result = await service.generate_checklist(citizen)

        assert result.total_eligible_schemes == 0
        assert "అందుబాటులో లేవు" in result.ai_summary_te

    def test_normalize_doc_key(self):
        """Test document key normalization."""
        service = ChecklistService(db=AsyncMock())
        assert service._normalize_doc_key("Aadhaar Card") == "aadhaar_card"
        assert service._normalize_doc_key("Ration Card Copy") == "ration_card"
        assert service._normalize_doc_key("Income Certificate") == "income_certificate"
        assert service._normalize_doc_key("Bank Passbook") == "bank_passbook"
        assert service._normalize_doc_key("Caste Certificate") == "caste_certificate"
        assert service._normalize_doc_key("Disability Certificate") == "disability_certificate"
        assert service._normalize_doc_key("Land pattadar passbook") == "land_document"

    def test_normalize_doc_key_unknown(self):
        """Test normalization of unknown document names."""
        service = ChecklistService(db=AsyncMock())
        result = service._normalize_doc_key("Custom Document")
        assert result == "custom_document"

    def test_rule_based_eligibility_age_check(self):
        """Test rule-based fallback eligibility — age filter."""
        service = ChecklistService(db=AsyncMock())
        scheme = self._make_mock_scheme(
            "test", "టెస్ట్", "Test",
            {"min_age": 18, "max_age": 60},
        )
        citizen = CitizenProfile(name="Test", age=65)
        results = service._rule_based_eligibility(citizen, [scheme])
        assert len(results) == 0  # too old

        citizen2 = CitizenProfile(name="Test", age=30)
        results2 = service._rule_based_eligibility(citizen2, [scheme])
        assert len(results2) == 1
        assert results2[0]["is_eligible"] is True

    def test_rule_based_eligibility_income_check(self):
        """Test rule-based fallback eligibility — income filter."""
        service = ChecklistService(db=AsyncMock())
        scheme = self._make_mock_scheme(
            "test", "టెస్ట్", "Test",
            {"max_income": 200000},
        )
        citizen = CitizenProfile(name="Test", income=300000)
        results = service._rule_based_eligibility(citizen, [scheme])
        assert len(results) == 0  # income too high

    def test_extract_documents_list(self):
        """Test document extraction from list format."""
        service = ChecklistService(db=AsyncMock())
        scheme = self._make_mock_scheme("test", "T", "T", docs=["aadhaar_card", "bank_passbook"])
        docs = service._extract_documents(scheme)
        assert "aadhaar_card" in docs
        assert "bank_passbook" in docs

    def test_extract_documents_empty(self):
        """Test document extraction when no documents specified."""
        service = ChecklistService(db=AsyncMock())
        scheme = self._make_mock_scheme("test", "T", "T", docs=None)
        docs = service._extract_documents(scheme)
        assert "aadhaar_card" in docs  # defaults

    def test_build_summary(self):
        """Test Telugu summary generation."""
        from app.schemas.checklist import SchemeDocumentGroup
        service = ChecklistService(db=AsyncMock())
        groups = [
            SchemeDocumentGroup(
                scheme_code="ysr_amma_vodi",
                scheme_name_te="అమ్మ ఒడి",
                scheme_name_en="Amma Vodi",
                is_eligible=True,
                documents=["aadhaar_card"],
            ),
        ]
        citizen = CitizenProfile(name="Test")
        summary = service._build_summary(citizen, groups, 3)
        assert "1 పథకాలకు" in summary
        assert "3 రకాల పత్రాలు" in summary

    def test_common_documents_has_telugu_names(self):
        """Verify all common documents have Telugu translations."""
        for key, (te, en) in COMMON_DOCUMENTS.items():
            assert te, f"Missing Telugu name for {key}"
            assert en, f"Missing English name for {key}"


# --- Schema Tests ---

class TestChecklistSchemas:
    """Tests for checklist Pydantic schemas."""

    def test_citizen_profile_minimal(self):
        """Test CitizenProfile with minimal data."""
        profile = CitizenProfile(name="Test")
        assert profile.name == "Test"
        assert profile.age is None
        assert profile.is_disabled is False

    def test_citizen_profile_full(self):
        """Test CitizenProfile with full data."""
        profile = CitizenProfile(
            name="రామ్మూర్తి",
            age=45,
            gender="male",
            income=150000,
            caste="BC",
            ration_card="white",
            occupation="farmer",
            district="Guntur",
            is_disabled=False,
            land_acres=2.5,
            has_school_children=True,
            num_children=2,
        )
        assert profile.age == 45
        assert profile.land_acres == 2.5

    def test_checklist_response_defaults(self):
        """Test DocumentChecklistResponse defaults."""
        response = DocumentChecklistResponse()
        assert response.total_eligible_schemes == 0
        assert response.common_documents == []
        assert response.scheme_documents == []
