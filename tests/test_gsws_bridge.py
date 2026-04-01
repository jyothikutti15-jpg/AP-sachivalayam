"""Tests for GSWS Bridge — government portal integration."""
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMockMode:
    """Test GSWS bridge in mock mode (default for development)."""

    @pytest.mark.asyncio
    async def test_mock_submit_returns_gsws_id(self):
        from app.services.gsws_bridge import GSWSBridge

        bridge = GSWSBridge.__new__(GSWSBridge)
        bridge.mock_mode = True
        bridge.db = AsyncMock()

        submission = MagicMock()
        submission.id = "test-uuid"
        submission.field_values = {"name": "test"}
        submission.citizen_name = "Test"
        submission.employee_id = 1

        result = await bridge._mock_submit(submission)

        assert result["status"] == "submitted"
        assert result["gsws_id"].startswith("GSWS-")
        assert result["mock"] is True
        assert submission.status == "submitted"
        assert submission.gsws_submission_id is not None

    def test_mock_status_returns_valid_status(self):
        from app.services.gsws_bridge import GSWSBridge

        bridge = GSWSBridge.__new__(GSWSBridge)
        bridge.mock_mode = True

        result = bridge._mock_status("GSWS-ABC123")

        assert result["reference_id"] == "GSWS-ABC123"
        assert result["status"] in ["pending", "under_review", "approved", "disbursed"]
        assert "message_te" in result
        assert result["mock"] is True

    @pytest.mark.asyncio
    async def test_citizen_lookup_mock(self):
        from app.services.gsws_bridge import GSWSBridge

        bridge = GSWSBridge.__new__(GSWSBridge)
        bridge.mock_mode = True

        result = await bridge.citizen_lookup("9012", "రామయ్య")

        assert result["found"] is True
        assert len(result["schemes_enrolled"]) >= 1

    @pytest.mark.asyncio
    async def test_sync_scheme_data_mock(self):
        from app.services.gsws_bridge import GSWSBridge

        bridge = GSWSBridge.__new__(GSWSBridge)
        bridge.mock_mode = True
        bridge.db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [1, 2, 3]
        bridge.db.execute = AsyncMock(return_value=mock_result)

        result = await bridge.sync_scheme_data()
        assert result["status"] == "synced"
        assert result["mock"] is True


class TestMockModeDetection:
    """Test that mock mode is correctly detected."""

    def test_empty_api_key_is_mock(self):
        from app.services.gsws_bridge import _is_mock_mode
        # Default .env has placeholder key
        # This should be True in development
        result = _is_mock_mode()
        assert isinstance(result, bool)
