"""
Comprehensive tests for Feature 1: Citizen-Facing Mode.

Tests citizen model, user detection, intent gating, greeting,
auto-registration, and the Citizens API.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.citizen import Citizen
from app.services.conversation_engine import CITIZEN_ALLOWED_INTENTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_citizen(**overrides):
    """Create a Citizen-like object with defaults."""
    defaults = dict(
        id=1,
        phone_number="+919876543210",
        name_te="రాము",
        name_en="Ramu",
        district="Guntur",
        mandal="Tenali",
        preferred_language="te",
        is_verified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    obj = MagicMock(spec=Citizen)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_employee(**overrides):
    """Create an Employee-like mock object."""
    from app.models.user import Employee
    defaults = dict(
        id=100,
        phone_number="+919000000001",
        name_te="సీత",
        name_en="Seetha",
        designation="WEA",
        department="Welfare",
        preferred_language="te",
        role="employee",
    )
    defaults.update(overrides)
    obj = MagicMock(spec=Employee)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# ===========================================================================
# TestCitizenModel
# ===========================================================================

class TestCitizenModel:
    """Tests for the Citizen SQLAlchemy model."""

    def test_citizen_tablename(self):
        assert Citizen.__tablename__ == "citizens"

    def test_citizen_defaults(self):
        c = Citizen(phone_number="+910000000000")
        assert c.name_te == "Unknown" or c.name_te is None  # default set at DB level
        assert c.is_verified is False or c.is_verified is None
        # The column default is "te"
        col = Citizen.__table__.columns["preferred_language"]
        assert col.default.arg == "te"

    def test_citizen_phone_required(self):
        col = Citizen.__table__.columns["phone_number"]
        assert col.nullable is False


# ===========================================================================
# TestUserDetection
# ===========================================================================

class TestUserDetection:
    """Tests for get_user_by_phone in app.core.security."""

    @pytest.mark.asyncio
    async def test_employee_detected_first(self):
        """When phone belongs to an employee, return (employee, 'employee')."""
        from app.core.security import get_user_by_phone

        employee = _make_employee()
        db = AsyncMock()

        with patch("app.core.security.get_employee_by_phone", new_callable=AsyncMock, return_value=employee):
            with patch("app.core.security.get_citizen_by_phone", new_callable=AsyncMock) as mock_cit:
                user, utype = await get_user_by_phone("+919000000001", db)
                assert utype == "employee"
                assert user is employee
                mock_cit.assert_not_called()

    @pytest.mark.asyncio
    async def test_citizen_detected(self):
        """Phone not in employees, found in citizens."""
        from app.core.security import get_user_by_phone

        citizen = _make_citizen()
        db = AsyncMock()

        with patch("app.core.security.get_employee_by_phone", new_callable=AsyncMock, return_value=None):
            with patch("app.core.security.get_citizen_by_phone", new_callable=AsyncMock, return_value=citizen):
                user, utype = await get_user_by_phone("+919876543210", db)
                assert utype == "citizen"
                assert user is citizen

    @pytest.mark.asyncio
    async def test_unknown_phone_returns_none(self):
        """Not in either table."""
        from app.core.security import get_user_by_phone

        db = AsyncMock()
        with patch("app.core.security.get_employee_by_phone", new_callable=AsyncMock, return_value=None):
            with patch("app.core.security.get_citizen_by_phone", new_callable=AsyncMock, return_value=None):
                user, utype = await get_user_by_phone("+910000000000", db)
                assert user is None
                assert utype is None

    @pytest.mark.asyncio
    async def test_employee_takes_priority(self):
        """Same phone in both tables — employee wins."""
        from app.core.security import get_user_by_phone

        employee = _make_employee(phone_number="+919999999999")
        citizen = _make_citizen(phone_number="+919999999999")
        db = AsyncMock()

        with patch("app.core.security.get_employee_by_phone", new_callable=AsyncMock, return_value=employee):
            with patch("app.core.security.get_citizen_by_phone", new_callable=AsyncMock, return_value=citizen):
                user, utype = await get_user_by_phone("+919999999999", db)
                assert utype == "employee"
                assert user is employee


# ===========================================================================
# TestCitizenIntentGating
# ===========================================================================

class TestCitizenIntentGating:
    """Citizens can only use read-only intents."""

    def test_scheme_query_allowed(self):
        assert "scheme_query" in CITIZEN_ALLOWED_INTENTS

    def test_eligibility_check_allowed(self):
        assert "eligibility_check" in CITIZEN_ALLOWED_INTENTS

    def test_status_check_allowed(self):
        assert "status_check" in CITIZEN_ALLOWED_INTENTS

    def test_greeting_allowed(self):
        assert "greeting" in CITIZEN_ALLOWED_INTENTS

    def test_help_allowed(self):
        assert "help" in CITIZEN_ALLOWED_INTENTS

    def test_form_help_blocked(self):
        assert "form_help" not in CITIZEN_ALLOWED_INTENTS

    def test_grievance_blocked(self):
        assert "grievance" not in CITIZEN_ALLOWED_INTENTS

    def test_task_query_blocked(self):
        assert "task_query" not in CITIZEN_ALLOWED_INTENTS


# ===========================================================================
# TestCitizenGreeting
# ===========================================================================

class TestCitizenGreeting:
    """Test citizen greeting message structure."""

    def _engine(self):
        from app.services.conversation_engine import ConversationEngine
        db = AsyncMock()
        with patch("app.services.conversation_engine.LLMRouter"), \
             patch("app.services.conversation_engine.SchemeAdvisor"), \
             patch("app.services.conversation_engine.WhatsAppService"):
            engine = ConversationEngine(db=db)
        return engine

    def test_citizen_greeting_telugu(self):
        engine = self._engine()
        citizen = _make_citizen(name_te="రాము")
        result = engine._build_citizen_greeting(citizen, "te")
        assert result["type"] == "list"
        assert "నమస్కారం" in result["text"]
        assert "రాము" in result["text"]
        assert result["button_text"] == "సేవలు చూడండి"

    def test_citizen_greeting_english(self):
        engine = self._engine()
        citizen = _make_citizen(name_en="Ramu")
        result = engine._build_citizen_greeting(citizen, "en")
        assert result["type"] == "list"
        assert "Welcome" in result["text"]
        assert "Ramu" in result["text"]
        assert result["button_text"] == "View Services"

    def test_citizen_greeting_has_3_options(self):
        engine = self._engine()
        citizen = _make_citizen()
        result = engine._build_citizen_greeting(citizen, "te")
        rows = result["sections"][0]["rows"]
        assert len(rows) == 3
        ids = {r["id"] for r in rows}
        assert "show_scheme_list" in ids
        assert "status_check" in ids
        assert "help_menu" in ids
        # Employee-only items should NOT be present
        assert "form_help" not in ids
        assert "grievance_file" not in ids
        assert "task_plan" not in ids


# ===========================================================================
# TestCitizenAutoRegistration
# ===========================================================================

class TestCitizenAutoRegistration:
    """Test auto-registration of unknown phone numbers as citizens."""

    def _engine(self):
        from app.services.conversation_engine import ConversationEngine
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        with patch("app.services.conversation_engine.LLMRouter"), \
             patch("app.services.conversation_engine.SchemeAdvisor"), \
             patch("app.services.conversation_engine.WhatsAppService"):
            engine = ConversationEngine(db=db)
        return engine

    @pytest.mark.asyncio
    async def test_unknown_phone_creates_citizen(self):
        engine = self._engine()
        citizen = await engine._auto_register_citizen("+919111111111", "Test")
        assert isinstance(citizen, Citizen)
        assert citizen.phone_number == "+919111111111"
        engine.db.add.assert_called_once()
        engine.db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_citizen_created_with_contact_name(self):
        engine = self._engine()
        citizen = await engine._auto_register_citizen("+919222222222", "Lakshmi")
        assert citizen.name_te == "Lakshmi"
        assert citizen.name_en == "Lakshmi"

    @pytest.mark.asyncio
    async def test_citizen_language_default_telugu(self):
        engine = self._engine()
        citizen = await engine._auto_register_citizen("+919333333333", "")
        # Citizen model defaults preferred_language to "te" via column default
        col = Citizen.__table__.columns["preferred_language"]
        assert col.default.arg == "te"


# ===========================================================================
# TestCitizenAPI
# ===========================================================================

class TestCitizenAPI:
    """Test Citizens REST API endpoints."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def app(self, mock_db):
        from fastapi import FastAPI
        from app.api.v1.router import api_v1_router
        from app.dependencies import get_db

        test_app = FastAPI()
        test_app.include_router(api_v1_router, prefix="/api/v1")

        async def override_get_db():
            yield mock_db

        test_app.dependency_overrides[get_db] = override_get_db
        return test_app

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app, raise_server_exceptions=False)

    def test_get_citizen_by_phone_found(self, client, mock_db):
        citizen_mock = MagicMock()
        citizen_mock.id = 1
        citizen_mock.phone_number = "+919876543210"
        citizen_mock.name_te = "రాము"
        citizen_mock.name_en = "Ramu"
        citizen_mock.district = "Guntur"
        citizen_mock.mandal = "Tenali"
        citizen_mock.preferred_language = "te"
        citizen_mock.is_verified = False
        citizen_mock.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = citizen_mock
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/citizens/+919876543210")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phone_number"] == "+919876543210"
        assert data["name_te"] == "రాము"

    def test_get_citizen_by_phone_not_found_404(self, client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/citizens/+910000000000")
        assert resp.status_code == 404

    def test_list_citizens_with_district_filter(self, client, mock_db):
        citizen1 = MagicMock()
        citizen1.id = 1
        citizen1.phone_number = "+919876543210"
        citizen1.name_te = "రాము"
        citizen1.name_en = "Ramu"
        citizen1.district = "Guntur"
        citizen1.mandal = "Tenali"
        citizen1.preferred_language = "te"
        citizen1.is_verified = False
        citizen1.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [citizen1]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/citizens/?district=Guntur")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["district"] == "Guntur"
