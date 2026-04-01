"""Tests for Offline Queue and Keyword Fallback."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestKeywordFallbackSearch:
    """Test offline-capable scheme search without LLM."""

    @pytest.mark.asyncio
    async def test_known_scheme_returns_summary(self):
        from app.services.offline_queue import KeywordFallbackSearch

        search = KeywordFallbackSearch.__new__(KeywordFallbackSearch)
        search.db = AsyncMock()

        # Mock scheme lookup
        mock_scheme = MagicMock()
        mock_scheme.name_te = "వైఎస్ఆర్ అమ్మ ఒడి"
        mock_scheme.name_en = "YSR Amma Vodi"
        mock_scheme.department = "School Education"
        mock_scheme.benefit_amount = "₹15,000"
        mock_scheme.description_te = "పిల్లలను బడికి పంపే తల్లులకు ₹15,000"
        mock_scheme.eligibility_criteria = {"income": "Below 10 lakhs"}
        mock_scheme.required_documents = {"mandatory": ["Aadhaar"]}
        mock_scheme.go_reference = "GO Ms. No. 47"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_scheme
        search.db.execute = AsyncMock(return_value=mock_result)

        result = await search._get_scheme_summary("YSR-AMMA-VODI", "te")

        assert result is not None
        assert "అమ్మ ఒడి" in result
        assert "₹15,000" in result
        assert "GO Ms. No. 47" in result


class TestQueueStats:
    """Test queue statistics."""

    @pytest.mark.asyncio
    async def test_get_queue_stats(self):
        from app.services.offline_queue import OfflineQueueService

        service = OfflineQueueService.__new__(OfflineQueueService)
        service.db = AsyncMock()

        # Mock counts
        mock_pending = MagicMock()
        mock_pending.scalar.return_value = 5
        mock_failed = MagicMock()
        mock_failed.scalar.return_value = 1
        mock_done = MagicMock()
        mock_done.scalar.return_value = 100

        service.db.execute = AsyncMock(side_effect=[mock_pending, mock_failed, mock_done])

        stats = await service.get_queue_stats()
        assert stats["pending"] == 5
        assert stats["failed"] == 1
        assert stats["completed"] == 100
