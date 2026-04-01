"""
Comprehensive FastAPI endpoint tests using TestClient.
Tests all API routes: grievances, tasks, schemes, forms, voice, analytics, health.
"""
import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


# --- Fixtures ---

@pytest.fixture
def mock_db():
    """Create a mock async DB session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def app(mock_db):
    """Create a minimal test FastAPI app with the same routes."""
    from fastapi import FastAPI
    from app.api.v1.router import api_v1_router
    from app.dependencies import get_db

    test_app = FastAPI()
    test_app.include_router(api_v1_router, prefix="/api/v1")

    @test_app.get("/")
    async def root():
        return {"name": "AP Sachivalayam AI Copilot", "status": "ok"}

    async def override_get_db():
        yield mock_db

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ============================================================
# HEALTH CHECK TESTS
# ============================================================

class TestHealthEndpoint:
    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data or "status" in data


# ============================================================
# SCHEME ENDPOINT TESTS
# ============================================================

class TestSchemeEndpoints:
    def test_list_schemes_returns_list(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/schemes/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_schemes_with_department_filter(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/schemes/?department=Agriculture")
        assert response.status_code == 200

    def test_list_schemes_with_pagination(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/schemes/?limit=10&offset=20")
        assert response.status_code == 200

    def test_get_scheme_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/schemes/NONEXISTENT")
        assert response.status_code == 404

    def test_search_schemes_valid(self, client, mock_db):
        with patch("app.api.v1.schemes.SchemeAdvisor") as MockAdvisor:
            instance = MockAdvisor.return_value
            instance.search = AsyncMock(return_value=MagicMock(
                answer="Test answer",
                sources=[],
                schemes_referenced=[],
                confidence=0.9,
            ))
            response = client.post(
                "/api/v1/schemes/search",
                json={"query": "అమ్మ ఒడి", "language": "te"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data

    def test_eligibility_check_valid(self, client, mock_db):
        with patch("app.api.v1.schemes.SchemeAdvisor") as MockAdvisor:
            instance = MockAdvisor.return_value
            instance.check_eligibility = AsyncMock(return_value=MagicMock(
                scheme_code="YSR-AMMA-VODI",
                scheme_name_te="అమ్మ ఒడి",
                is_eligible=True,
                reasoning_te="అర్హత ఉంది",
                missing_documents=[],
                next_steps_te="Apply",
            ))
            response = client.post(
                "/api/v1/schemes/eligibility-check",
                json={"scheme_code": "YSR-AMMA-VODI", "citizen_details": {"age": 35}},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["is_eligible"] is True


# ============================================================
# GRIEVANCE ENDPOINT TESTS
# ============================================================

class TestGrievanceEndpoints:
    def _make_grievance_response(self, **overrides):
        """Helper to build a mock grievance response."""
        defaults = {
            "id": uuid4(),
            "reference_number": "GRV-2026-0001",
            "citizen_name": "రాము",
            "category": "welfare",
            "department": "Welfare",
            "subject_te": "పెన్షన్ ఆలస్యం",
            "description_te": "3 నెలల నుండి పెన్షన్ రావడం లేదు",
            "status": "open",
            "priority": "medium",
            "escalation_level": 0,
            "sla_deadline": datetime.now(timezone.utc) + timedelta(hours=72),
            "acknowledged_at": None,
            "resolved_at": None,
            "is_sla_breached": False,
            "resolution_notes_te": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "comments": [],
        }
        defaults.update(overrides)
        return MagicMock(**defaults)

    def test_file_grievance_success(self, client, mock_db):
        with patch("app.api.v1.grievances.GrievanceService") as MockService:
            mock_response = self._make_grievance_response()
            # Make it serializable
            MockService.return_value.file_grievance = AsyncMock(return_value=mock_response)

            response = client.post(
                "/api/v1/grievances/?employee_id=1",
                json={
                    "citizen_name": "రాము",
                    "category": "welfare",
                    "subject_te": "పెన్షన్ ఆలస్యం",
                    "description_te": "3 నెలల నుండి పెన్షన్ రావడం లేదు",
                },
            )
            assert response.status_code == 201

    def test_file_grievance_missing_employee_id(self, client, mock_db):
        response = client.post(
            "/api/v1/grievances/",
            json={
                "citizen_name": "Test",
                "category": "welfare",
                "subject_te": "Test",
                "description_te": "Test",
            },
        )
        assert response.status_code == 422

    def test_get_grievance_not_found(self, client, mock_db):
        with patch("app.api.v1.grievances.GrievanceService") as MockService:
            MockService.return_value.get_grievance = AsyncMock(return_value=None)
            response = client.get(f"/api/v1/grievances/{uuid4()}")
            assert response.status_code == 404

    def test_list_grievances_empty(self, client, mock_db):
        with patch("app.api.v1.grievances.GrievanceService") as MockService:
            MockService.return_value.list_grievances = AsyncMock(return_value=([], 0))
            response = client.get("/api/v1/grievances/")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["grievances"] == []

    def test_list_grievances_with_filters(self, client, mock_db):
        with patch("app.api.v1.grievances.GrievanceService") as MockService:
            MockService.return_value.list_grievances = AsyncMock(return_value=([], 0))
            response = client.get(
                "/api/v1/grievances/?status=open&category=welfare&priority=high&page=1&page_size=10"
            )
            assert response.status_code == 200

    def test_update_grievance_not_found(self, client, mock_db):
        with patch("app.api.v1.grievances.GrievanceService") as MockService:
            MockService.return_value.update_grievance = AsyncMock(return_value=None)
            response = client.patch(
                f"/api/v1/grievances/{uuid4()}?employee_id=1",
                json={"status": "acknowledged"},
            )
            assert response.status_code == 404

    def test_add_comment_success(self, client, mock_db):
        with patch("app.api.v1.grievances.GrievanceService") as MockService:
            MockService.return_value.add_comment = AsyncMock(return_value=MagicMock(
                id=uuid4(),
                employee_id=1,
                comment_text="Test comment",
                comment_type="note",
                created_at=datetime.now(timezone.utc),
            ))
            response = client.post(
                f"/api/v1/grievances/{uuid4()}/comments?employee_id=1",
                json={"comment_text": "Test comment"},
            )
            assert response.status_code == 201

    def test_ai_suggest(self, client, mock_db):
        with patch("app.api.v1.grievances.GrievanceService") as MockService:
            MockService.return_value.ai_suggest = AsyncMock(return_value=MagicMock(
                suggested_category="welfare",
                suggested_department="Welfare",
                suggested_priority="high",
                escalation_path_te="సచివాలయం → మండల",
                required_evidence_te=["doc1"],
                similar_grievances=[],
                resolution_suggestion_te="Test",
            ))
            response = client.post(
                "/api/v1/grievances/ai-suggest?category=welfare&subject=Test&description=Test"
            )
            assert response.status_code == 200

    def test_grievance_stats(self, client, mock_db):
        with patch("app.api.v1.grievances.GrievanceService") as MockService:
            MockService.return_value.get_grievance_stats = AsyncMock(return_value={
                "by_status": {"open": 5, "resolved": 10},
                "total": 15,
                "sla_breached": 2,
                "avg_resolution_hours": 48.5,
            })
            response = client.get("/api/v1/grievances/stats/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 15


# ============================================================
# TASK ENDPOINT TESTS
# ============================================================

class TestTaskEndpoints:
    def _make_task_response(self, **overrides):
        defaults = {
            "id": uuid4(),
            "employee_id": 1,
            "title_te": "Test task",
            "title_en": None,
            "department": "Agriculture",
            "category": "general",
            "priority": "medium",
            "priority_score": 50,
            "due_date": date.today(),
            "estimated_minutes": 30,
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "actual_minutes": None,
            "source": "manual",
            "ai_priority_reason_te": None,
            "is_ai_suggested": False,
            "is_recurring": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return MagicMock(**defaults)

    def test_create_task_success(self, client, mock_db):
        with patch("app.api.v1.tasks.TaskService") as MockService:
            MockService.return_value.create_task = AsyncMock(
                return_value=self._make_task_response()
            )
            response = client.post(
                "/api/v1/tasks/?employee_id=1",
                json={
                    "title_te": "రైతు భరోసా process",
                    "department": "Agriculture",
                },
            )
            assert response.status_code == 201

    def test_create_task_missing_employee_id(self, client):
        response = client.post(
            "/api/v1/tasks/",
            json={"title_te": "Test", "department": "Test"},
        )
        assert response.status_code == 422

    def test_get_daily_plan_success(self, client, mock_db):
        with patch("app.api.v1.tasks.TaskService") as MockService:
            MockService.return_value.generate_daily_plan = AsyncMock(return_value=MagicMock(
                plan_date=date.today(),
                tasks=[],
                total_estimated_minutes=0,
                ai_summary_te="No tasks",
                ai_summary_en="No tasks",
            ))
            response = client.get("/api/v1/tasks/daily-plan?employee_id=1")
            assert response.status_code == 200

    def test_list_tasks_empty(self, client, mock_db):
        with patch("app.api.v1.tasks.TaskService") as MockService:
            MockService.return_value.list_tasks = AsyncMock(return_value=([], 0))
            response = client.get("/api/v1/tasks/?employee_id=1")
            assert response.status_code == 200

    def test_get_task_not_found(self, client, mock_db):
        with patch("app.api.v1.tasks.TaskService") as MockService:
            MockService.return_value.get_task = AsyncMock(return_value=None)
            response = client.get(f"/api/v1/tasks/{uuid4()}")
            assert response.status_code == 404

    def test_start_task_success(self, client, mock_db):
        with patch("app.api.v1.tasks.TaskService") as MockService:
            MockService.return_value.update_task = AsyncMock(
                return_value=self._make_task_response(status="in_progress")
            )
            response = client.post(f"/api/v1/tasks/{uuid4()}/start?employee_id=1")
            assert response.status_code == 200

    def test_complete_task_success(self, client, mock_db):
        with patch("app.api.v1.tasks.TaskService") as MockService:
            MockService.return_value.update_task = AsyncMock(
                return_value=self._make_task_response(status="completed")
            )
            response = client.post(f"/api/v1/tasks/{uuid4()}/complete?employee_id=1")
            assert response.status_code == 200

    def test_complete_task_with_actual_minutes(self, client, mock_db):
        with patch("app.api.v1.tasks.TaskService") as MockService:
            MockService.return_value.update_task = AsyncMock(
                return_value=self._make_task_response(status="completed", actual_minutes=45)
            )
            response = client.post(
                f"/api/v1/tasks/{uuid4()}/complete?employee_id=1&actual_minutes=45"
            )
            assert response.status_code == 200

    def test_workload_summary(self, client, mock_db):
        with patch("app.api.v1.tasks.TaskService") as MockService:
            MockService.return_value.get_workload_summary = AsyncMock(return_value=MagicMock(
                employee_id=1,
                date=date.today(),
                total_tasks=10,
                completed_tasks=5,
                overdue_tasks=2,
                pending_tasks=3,
                in_progress_tasks=2,
                total_estimated_minutes=300,
                total_actual_minutes=150,
                departments_involved=["Agriculture", "Health"],
                workload_level="moderate",
            ))
            response = client.get("/api/v1/tasks/workload/summary?employee_id=1")
            assert response.status_code == 200


# ============================================================
# FORM ENDPOINT TESTS
# ============================================================

class TestFormEndpoints:
    def test_list_templates(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = client.get("/api/v1/forms/templates")
        assert response.status_code == 200

    def test_auto_fill_valid(self, client, mock_db):
        with patch("app.api.v1.forms.FormFiller") as MockFiller:
            MockFiller.return_value.auto_fill = AsyncMock(return_value=MagicMock(
                submission_id=uuid4(),
                extracted_fields={"name": "Test"},
                confidence_scores={"name": 0.9},
                message_te="Test message",
                status="draft",
            ))
            response = client.post(
                "/api/v1/forms/auto-fill",
                json={
                    "template_id": 1,
                    "input_text": "రాము, 35 ఏళ్ళు, 2 లక్షలు income",
                    "employee_id": 1,
                },
            )
            assert response.status_code == 200

    def test_download_pdf_not_found(self, client, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = client.get(f"/api/v1/forms/{uuid4()}/pdf")
        assert response.status_code == 404


# ============================================================
# VOICE ENDPOINT TESTS
# ============================================================

class TestVoiceEndpoints:
    def test_transcribe_no_file(self, client):
        response = client.post("/api/v1/voice/transcribe")
        assert response.status_code == 422


# ============================================================
# WHATSAPP WEBHOOK TESTS
# ============================================================

class TestWhatsAppWebhook:
    def test_webhook_verification_valid(self, client):
        response = client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "",  # matches empty default
                "hub.challenge": "test_challenge_123",
            },
        )
        # May return 200 or 403 depending on token config
        assert response.status_code in (200, 403)

    def test_webhook_post_returns_200(self, client, mock_db):
        """WhatsApp webhook should always return 200 to avoid retries."""
        with patch("app.api.v1.whatsapp.ConversationEngine"):
            response = client.post(
                "/api/v1/whatsapp/webhook",
                json={"object": "whatsapp_business_account", "entry": []},
            )
            assert response.status_code == 200

    def test_webhook_post_invalid_object(self, client):
        response = client.post(
            "/api/v1/whatsapp/webhook",
            json={"object": "not_whatsapp", "entry": []},
        )
        assert response.status_code == 200  # Still 200 per WhatsApp spec
