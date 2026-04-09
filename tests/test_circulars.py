"""Tests for GO/Circular Knowledge Base (Feature 9)."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.circular import Circular
from app.schemas.circular import (
    CircularCreate,
    CircularResponse,
    CircularSearchRequest,
    CircularSearchResponse,
)
from app.services.circular_service import CircularService


class TestCircularService:
    """Tests for the circular/GO knowledge base service."""

    def _make_mock_circular(self, ref, title_te, dept, issued, **kwargs):
        circular = MagicMock(spec=Circular)
        circular.id = uuid.uuid4()
        circular.reference_number = ref
        circular.title_te = title_te
        circular.title_en = kwargs.get("title_en", ref)
        circular.content_te = kwargs.get("content_te")
        circular.content_en = kwargs.get("content_en")
        circular.summary_te = kwargs.get("summary_te")
        circular.summary_en = kwargs.get("summary_en")
        circular.department = dept
        circular.category = kwargs.get("category", "go")
        circular.scheme_code = kwargs.get("scheme_code")
        circular.issued_date = issued
        circular.effective_date = kwargs.get("effective_date")
        circular.impact_level = kwargs.get("impact_level", "normal")
        circular.key_changes = kwargs.get("key_changes")
        circular.tags = kwargs.get("tags")
        circular.is_active = True
        circular.source_url = None
        circular.view_count = 0
        return circular

    @pytest.mark.asyncio
    async def test_search_with_results(self):
        """Test circular search that finds matching GOs."""
        db = AsyncMock()
        circulars = [
            self._make_mock_circular(
                "G.O.Ms.No.21",
                "అమ్మ ఒడి పథకం ఆదాయ పరిమితి పెంపు",
                "Education",
                date(2026, 3, 1),
                content_te="ఆదాయ పరిమితి 2 లక్షల నుండి 2.5 లక్షలకు పెంచబడింది",
                scheme_code="ysr_amma_vodi",
            ),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = circulars
        db.execute = AsyncMock(return_value=mock_result)

        service = CircularService(db=db)
        with patch.object(service.llm, 'call_claude', return_value="అమ్మ ఒడి ఆదాయ పరిమితి పెరిగింది"):
            result = await service.search(query="అమ్మ ఒడి")

        assert isinstance(result, CircularSearchResponse)
        assert result.confidence > 0
        assert len(result.circulars_referenced) == 1
        assert result.circulars_referenced[0].reference_number == "G.O.Ms.No.21"

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Test circular search with no matches."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        service = CircularService(db=db)
        result = await service.search(query="nonexistent GO")

        assert result.confidence == 0.0
        assert len(result.circulars_referenced) == 0

    @pytest.mark.asyncio
    async def test_search_with_department_filter(self):
        """Test circular search filtered by department."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        service = CircularService(db=db)
        result = await service.search(
            query="test", department="Education"
        )
        assert isinstance(result, CircularSearchResponse)

    @pytest.mark.asyncio
    async def test_search_with_date_range(self):
        """Test circular search with date filters."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        service = CircularService(db=db)
        result = await service.search(
            query="test",
            from_date=date(2026, 1, 1),
            to_date=date(2026, 3, 31),
        )
        assert isinstance(result, CircularSearchResponse)

    @pytest.mark.asyncio
    async def test_create_circular(self):
        """Test creating a new circular."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        service = CircularService(db=db)
        data = CircularCreate(
            reference_number="G.O.Rt.No.100",
            title_te="కొత్త పథకం ప్రారంభం",
            title_en="New Scheme Launch",
            department="Welfare",
            issued_date=date(2026, 4, 1),
            impact_level="high",
            tags=["new_scheme"],
        )
        result = await service.create_circular(data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_reference(self):
        """Test fetching a circular by reference number."""
        db = AsyncMock()
        circular = self._make_mock_circular(
            "G.O.Ms.No.50", "టెస్ట్ GO", "Health", date(2026, 2, 15)
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = circular
        db.execute = AsyncMock(return_value=mock_result)

        service = CircularService(db=db)
        result = await service.get_by_reference("G.O.Ms.No.50")
        assert result is not None
        assert result.reference_number == "G.O.Ms.No.50"

    @pytest.mark.asyncio
    async def test_get_by_reference_not_found(self):
        """Test fetching a non-existent circular."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        service = CircularService(db=db)
        result = await service.get_by_reference("NONEXISTENT")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_recent(self):
        """Test listing recent circulars."""
        db = AsyncMock()
        circulars = [
            self._make_mock_circular("GO.1", "T1", "Education", date(2026, 4, 1)),
            self._make_mock_circular("GO.2", "T2", "Health", date(2026, 3, 28)),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = circulars
        db.execute = AsyncMock(return_value=mock_result)

        service = CircularService(db=db)
        result = await service.list_recent(limit=10)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_auto_summarize_success(self):
        """Test AI summarization of a GO."""
        db = AsyncMock()
        service = CircularService(db=db)

        mock_response = '{"summary_te": "సారాంశం", "summary_en": "Summary", "key_changes": [], "tags": ["test"]}'
        with patch.object(service.llm, 'call_claude_structured', return_value=mock_response):
            result = await service.auto_summarize("GO content here")

        assert result["summary_te"] == "సారాంశం"
        assert "test" in result["tags"]

    @pytest.mark.asyncio
    async def test_auto_summarize_failure(self):
        """Test AI summarization fallback on error."""
        db = AsyncMock()
        service = CircularService(db=db)

        with patch.object(service.llm, 'call_claude_structured', side_effect=Exception("LLM down")):
            result = await service.auto_summarize("GO content")

        assert "లోపం" in result["summary_te"]

    def test_format_circular_context(self):
        """Test circular context formatting for LLM."""
        db = AsyncMock()
        service = CircularService(db=db)
        circulars = [
            self._make_mock_circular(
                "GO.1", "టెస్ట్", "Education", date(2026, 1, 1),
                content_te="కంటెంట్",
                key_changes=[{"field": "income", "description_te": "మార్పు"}],
            ),
        ]
        context = service._format_circular_context(circulars)
        assert "GO.1" in context
        assert "Education" in context


# --- Schema Tests ---

class TestCircularSchemas:
    """Tests for circular Pydantic schemas."""

    def test_circular_create(self):
        data = CircularCreate(
            reference_number="G.O.Ms.No.1",
            title_te="టెస్ట్",
            department="Education",
            issued_date=date(2026, 4, 1),
        )
        assert data.category == "go"
        assert data.impact_level == "normal"

    def test_circular_search_request(self):
        req = CircularSearchRequest(query="అమ్మ ఒడి")
        assert req.language == "te"
        assert req.department is None

    def test_circular_response_from_attributes(self):
        resp = CircularResponse(
            id="test-id",
            reference_number="GO.1",
            title_te="టెస్ట్",
            department="Education",
            category="go",
            issued_date=date(2026, 1, 1),
            impact_level="normal",
            is_active=True,
        )
        assert resp.reference_number == "GO.1"
