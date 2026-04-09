"""Tests for Citizen Follow-up Reminders (Feature 10)."""

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.reminder import CitizenReminder
from app.schemas.reminder import (
    AutoReminderRequest,
    ReminderCreate,
    ReminderResponse,
    ReminderStatsResponse,
    ReminderUpdate,
)
from app.services.reminder_service import ReminderService, REMINDER_TEMPLATES


class TestReminderService:
    """Tests for the citizen reminder service."""

    def _make_mock_reminder(self, **kwargs):
        reminder = MagicMock(spec=CitizenReminder)
        reminder.id = kwargs.get("id", uuid.uuid4())
        reminder.employee_id = kwargs.get("employee_id", 1)
        reminder.secretariat_id = kwargs.get("secretariat_id")
        reminder.citizen_name = kwargs.get("citizen_name", "రామ్మూర్తి")
        reminder.citizen_phone = kwargs.get("citizen_phone", "9876543210")
        reminder.reminder_type = kwargs.get("reminder_type", "pending_documents")
        reminder.scheme_code = kwargs.get("scheme_code", "ysr_amma_vodi")
        reminder.scheme_name_te = kwargs.get("scheme_name_te", "అమ్మ ఒడి")
        reminder.message_te = kwargs.get("message_te", "Test message")
        reminder.message_en = kwargs.get("message_en")
        reminder.pending_items = kwargs.get("pending_items")
        reminder.reminder_date = kwargs.get("reminder_date", date.today())
        reminder.reminder_time = kwargs.get("reminder_time", "09:00")
        reminder.is_recurring = kwargs.get("is_recurring", False)
        reminder.recurrence_rule = kwargs.get("recurrence_rule")
        reminder.status = kwargs.get("status", "scheduled")
        reminder.sent_at = kwargs.get("sent_at")
        reminder.send_count = kwargs.get("send_count", 0)
        reminder.max_sends = kwargs.get("max_sends", 3)
        reminder.priority = kwargs.get("priority", "medium")
        reminder.created_at = kwargs.get("created_at", datetime.utcnow())
        return reminder

    @pytest.mark.asyncio
    async def test_create_reminder(self):
        """Test creating a basic reminder."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Mock scheme lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "అమ్మ ఒడి"
        db.execute = AsyncMock(return_value=mock_result)

        service = ReminderService(db=db)
        data = ReminderCreate(
            employee_id=1,
            citizen_name="రామ్మూర్తి",
            citizen_phone="9876543210",
            reminder_type="pending_documents",
            scheme_code="ysr_amma_vodi",
            message_te="పత్రాలు పెండింగ్‌లో ఉన్నాయి",
            reminder_date=date.today() + timedelta(days=3),
            priority="high",
        )
        result = await service.create_reminder(data)
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_generate_reminders(self):
        """Test auto-generating reminders from missing documents."""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()

        # Mock scheme lookup
        mock_scheme = MagicMock()
        mock_scheme.name_te = "అమ్మ ఒడి"
        mock_result_scheme = MagicMock()
        mock_result_scheme.scalar_one_or_none.return_value = mock_scheme

        # For reminder creation, scheme name lookup
        mock_result_name = MagicMock()
        mock_result_name.scalar_one_or_none.return_value = "అమ్మ ఒడి"

        db.execute = AsyncMock(side_effect=[mock_result_scheme, mock_result_name, mock_result_name])

        service = ReminderService(db=db)
        request = AutoReminderRequest(
            citizen_name="రామ్మూర్తి",
            citizen_phone="9876543210",
            employee_id=1,
            scheme_code="ysr_amma_vodi",
            missing_documents=["income_certificate", "caste_certificate"],
            deadline=date.today() + timedelta(days=15),
        )
        reminders = await service.auto_generate_reminders(request)

        # Should create at least 1 reminder (3 days from now)
        assert len(reminders) >= 1
        assert db.add.called

    @pytest.mark.asyncio
    async def test_auto_generate_no_missing_docs(self):
        """Test auto-generate with no missing documents creates no reminders."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(name_te="Test")
        db.execute = AsyncMock(return_value=mock_result)

        service = ReminderService(db=db)
        request = AutoReminderRequest(
            citizen_name="Test",
            citizen_phone="9876543210",
            employee_id=1,
            scheme_code="test",
            missing_documents=[],
        )
        reminders = await service.auto_generate_reminders(request)
        assert len(reminders) == 0

    @pytest.mark.asyncio
    async def test_list_reminders(self):
        """Test listing reminders with filters."""
        db = AsyncMock()
        mock_reminders = [
            self._make_mock_reminder(status="scheduled"),
            self._make_mock_reminder(status="sent"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_reminders
        db.execute = AsyncMock(return_value=mock_result)

        service = ReminderService(db=db)
        result = await service.list_reminders(employee_id=1)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_update_reminder_status(self):
        """Test updating a reminder's status."""
        db = AsyncMock()
        reminder = self._make_mock_reminder(status="scheduled")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = reminder
        db.execute = AsyncMock(return_value=mock_result)

        service = ReminderService(db=db)
        update = ReminderUpdate(status="cancelled")
        result = await service.update_reminder(str(reminder.id), update)
        assert result.status == "cancelled"

    @pytest.mark.asyncio
    async def test_update_reminder_not_found(self):
        """Test updating a non-existent reminder."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        service = ReminderService(db=db)
        result = await service.update_reminder(str(uuid.uuid4()), ReminderUpdate(status="cancelled"))
        assert result is None

    @pytest.mark.asyncio
    async def test_get_due_reminders(self):
        """Test getting reminders due today."""
        db = AsyncMock()
        due_reminders = [
            self._make_mock_reminder(
                reminder_date=date.today(),
                status="scheduled",
                priority="urgent",
            ),
            self._make_mock_reminder(
                reminder_date=date.today(),
                status="scheduled",
                priority="medium",
            ),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = due_reminders
        db.execute = AsyncMock(return_value=mock_result)

        service = ReminderService(db=db)
        result = await service.get_due_reminders()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_mark_sent(self):
        """Test marking a reminder as sent."""
        db = AsyncMock()
        reminder = self._make_mock_reminder(send_count=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = reminder
        db.execute = AsyncMock(return_value=mock_result)

        service = ReminderService(db=db)
        await service.mark_sent(str(reminder.id))
        assert reminder.status == "sent"
        assert reminder.send_count == 1

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting reminder statistics."""
        db = AsyncMock()

        # Mock status counts
        mock_status_rows = [
            MagicMock(status="scheduled", count=10),
            MagicMock(status="sent", count=5),
            MagicMock(status="completed", count=3),
        ]
        mock_status_result = MagicMock()
        mock_status_result.all.return_value = mock_status_rows

        # Mock type counts
        mock_type_rows = [
            MagicMock(reminder_type="pending_documents", count=8),
            MagicMock(reminder_type="renewal_deadline", count=7),
        ]
        mock_type_result = MagicMock()
        mock_type_result.all.return_value = mock_type_rows

        db.execute = AsyncMock(side_effect=[mock_status_result, mock_type_result])

        service = ReminderService(db=db)
        result = await service.get_stats()
        assert isinstance(result, ReminderStatsResponse)
        assert result.total_scheduled == 10
        assert result.total_sent == 5


# --- Template Tests ---

class TestReminderTemplates:
    """Tests for reminder message templates."""

    def test_pending_documents_template(self):
        msg = REMINDER_TEMPLATES["pending_documents"].format(
            citizen_name="రామ్మూర్తి",
            scheme_name="అమ్మ ఒడి",
            documents="ఆదాయ ధృవీకరణ పత్రం, కులధృవీకరణ పత్రం",
            deadline="15-04-2026",
        )
        assert "రామ్మూర్తి" in msg
        assert "అమ్మ ఒడి" in msg
        assert "15-04-2026" in msg

    def test_renewal_deadline_template(self):
        msg = REMINDER_TEMPLATES["renewal_deadline"].format(
            citizen_name="లక్ష్మి",
            scheme_name="చేయూత",
            deadline="30-06-2026",
        )
        assert "లక్ష్మి" in msg
        assert "రెన్యూవల్" in msg

    def test_disbursement_date_template(self):
        msg = REMINDER_TEMPLATES["disbursement_date"].format(
            citizen_name="వెంకటేష్",
            scheme_name="రైతు భరోసా",
            date="01-05-2026",
        )
        assert "వెంకటేష్" in msg
        assert "నగదు జమ" in msg


# --- Schema Tests ---

class TestReminderSchemas:
    """Tests for reminder Pydantic schemas."""

    def test_reminder_create(self):
        data = ReminderCreate(
            employee_id=1,
            citizen_name="Test",
            citizen_phone="9876543210",
            reminder_type="pending_documents",
            message_te="Test message",
            reminder_date=date.today(),
        )
        assert data.priority == "medium"
        assert data.reminder_time == "09:00"
        assert data.is_recurring is False

    def test_auto_reminder_request(self):
        req = AutoReminderRequest(
            citizen_name="Test",
            citizen_phone="9876543210",
            employee_id=1,
            scheme_code="ysr_amma_vodi",
            missing_documents=["income_certificate"],
        )
        assert len(req.missing_documents) == 1

    def test_reminder_update_partial(self):
        update = ReminderUpdate(status="cancelled")
        assert update.status == "cancelled"
        assert update.message_te is None

    def test_reminder_stats_defaults(self):
        stats = ReminderStatsResponse()
        assert stats.total_scheduled == 0
        assert stats.by_type == {}
