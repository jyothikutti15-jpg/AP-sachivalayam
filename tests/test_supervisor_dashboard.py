"""Tests for the Supervisor Dashboard API — mandal/district overviews,
secretariat rankings, SLA breach alerts, low-performing detection, employee drill-down."""
import uuid
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_secretariat(id_val, name_en, gsws_code, mandal="Mangalagiri", district="Guntur"):
    sec = MagicMock()
    sec.id = id_val
    sec.name_en = name_en
    sec.gsws_code = gsws_code
    sec.mandal = mandal
    sec.district = district
    return sec


def _make_employee(id_val, name_te="టెస్ట్", name_en="Test", designation="VRO",
                   department="Revenue", role="employee", secretariat_id=1):
    emp = MagicMock()
    emp.id = id_val
    emp.name_te = name_te
    emp.name_en = name_en
    emp.designation = designation
    emp.department = department
    emp.role = role
    emp.secretariat_id = secretariat_id
    return emp


def _make_grievance(id_val=None, status="open", priority="medium", category="welfare",
                    department="Welfare", sla_deadline=None, escalation_level=0,
                    reference_number="GRV-2026-0001", citizen_name="Ramesh"):
    g = MagicMock()
    g.id = id_val or uuid.uuid4()
    g.reference_number = reference_number
    g.citizen_name = citizen_name
    g.category = category
    g.department = department
    g.priority = priority
    g.status = status
    g.sla_deadline = sla_deadline or (datetime.now(timezone.utc) - timedelta(hours=10))
    g.escalation_level = escalation_level
    g.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    return g


Row = namedtuple("Row", ["total", "resolved", "open", "sla_breached"])
TaskRow = namedtuple("TaskRow", ["total", "completed", "pending"])
DistrictRow = namedtuple("DistrictRow", ["total", "resolved", "sla_breached"])
LowPerfRow = namedtuple("LowPerfRow", ["total", "completed"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    from app.services.supervisor_service import SupervisorService
    return SupervisorService(mock_db)


# ---------------------------------------------------------------------------
# TestMandalOverview
# ---------------------------------------------------------------------------

class TestMandalOverview:
    @pytest.mark.asyncio
    async def test_mandal_overview_returns_stats(self, mock_db, service):
        """Mandal overview should return grievance and task aggregates."""
        secs = [_make_secretariat(1, "Sec A", "GS001"), _make_secretariat(2, "Sec B", "GS002")]

        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        grv_row = Row(total=20, resolved=15, open=3, sla_breached=2)
        grv_mock = MagicMock()
        grv_mock.one.return_value = grv_row

        task_row = TaskRow(total=50, completed=40, pending=10)
        task_mock = MagicMock()
        task_mock.one.return_value = task_row

        emp_mock = MagicMock()
        emp_mock.scalar.return_value = 12

        mock_db.execute = AsyncMock(side_effect=[sec_mock, grv_mock, task_mock, emp_mock])

        result = await service.get_mandal_overview("Mangalagiri", days=30)

        assert result["mandal"] == "Mangalagiri"
        assert result["secretariat_count"] == 2
        assert result["employee_count"] == 12
        assert result["grievances"]["total"] == 20
        assert result["grievances"]["resolved"] == 15
        assert result["tasks"]["completed"] == 40

    @pytest.mark.asyncio
    async def test_mandal_overview_no_secretariats(self, mock_db, service):
        """When no secretariats exist for the mandal, return error."""
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=sec_mock)

        result = await service.get_mandal_overview("NonExistent")
        assert result["secretariat_count"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_mandal_overview_resolution_rate(self, mock_db, service):
        """Resolution rate should be (resolved / total) * 100."""
        secs = [_make_secretariat(1, "Sec A", "GS001")]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        grv_row = Row(total=200, resolved=150, open=30, sla_breached=20)
        grv_mock = MagicMock()
        grv_mock.one.return_value = grv_row

        task_row = TaskRow(total=100, completed=80, pending=20)
        task_mock = MagicMock()
        task_mock.one.return_value = task_row

        emp_mock = MagicMock()
        emp_mock.scalar.return_value = 5

        mock_db.execute = AsyncMock(side_effect=[sec_mock, grv_mock, task_mock, emp_mock])

        result = await service.get_mandal_overview("Mangalagiri")
        assert result["grievances"]["resolution_rate"] == 75.0
        assert result["tasks"]["completion_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_mandal_overview_zero_grievances(self, mock_db, service):
        """Zero grievances should give 0.0 rate, not division error."""
        secs = [_make_secretariat(1, "Sec A", "GS001")]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        grv_row = Row(total=0, resolved=0, open=0, sla_breached=0)
        grv_mock = MagicMock()
        grv_mock.one.return_value = grv_row

        task_row = TaskRow(total=0, completed=0, pending=0)
        task_mock = MagicMock()
        task_mock.one.return_value = task_row

        emp_mock = MagicMock()
        emp_mock.scalar.return_value = 2

        mock_db.execute = AsyncMock(side_effect=[sec_mock, grv_mock, task_mock, emp_mock])

        result = await service.get_mandal_overview("Mangalagiri")
        assert result["grievances"]["resolution_rate"] == 0.0
        assert result["tasks"]["completion_rate"] == 0.0


# ---------------------------------------------------------------------------
# TestDistrictOverview
# ---------------------------------------------------------------------------

class TestDistrictOverview:
    @pytest.mark.asyncio
    async def test_district_overview_returns_stats(self, mock_db, service):
        secs = [
            _make_secretariat(1, "Sec A", "GS001", mandal="Mangalagiri"),
            _make_secretariat(2, "Sec B", "GS002", mandal="Tadepalli"),
        ]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        grv_row = DistrictRow(total=100, resolved=80, sla_breached=5)
        grv_mock = MagicMock()
        grv_mock.one.return_value = grv_row

        emp_mock = MagicMock()
        emp_mock.scalar.return_value = 25

        mock_db.execute = AsyncMock(side_effect=[sec_mock, grv_mock, emp_mock])

        result = await service.get_district_overview("Guntur")
        assert result["district"] == "Guntur"
        assert result["secretariat_count"] == 2
        assert result["grievances"]["total"] == 100

    @pytest.mark.asyncio
    async def test_district_overview_counts_mandals(self, mock_db, service):
        secs = [
            _make_secretariat(1, "A", "G1", mandal="M1"),
            _make_secretariat(2, "B", "G2", mandal="M2"),
            _make_secretariat(3, "C", "G3", mandal="M1"),
        ]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        grv_row = DistrictRow(total=10, resolved=5, sla_breached=1)
        grv_mock = MagicMock()
        grv_mock.one.return_value = grv_row

        emp_mock = MagicMock()
        emp_mock.scalar.return_value = 10

        mock_db.execute = AsyncMock(side_effect=[sec_mock, grv_mock, emp_mock])

        result = await service.get_district_overview("Guntur")
        assert result["mandal_count"] == 2  # M1, M2 unique

    @pytest.mark.asyncio
    async def test_district_overview_no_secretariats(self, mock_db, service):
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=sec_mock)

        result = await service.get_district_overview("NonExistent")
        assert result["secretariat_count"] == 0
        assert "error" in result


# ---------------------------------------------------------------------------
# TestSecretariatRankings
# ---------------------------------------------------------------------------

class TestSecretariatRankings:
    @pytest.mark.asyncio
    async def test_rankings_sorted_descending(self, mock_db, service):
        secs = [
            _make_secretariat(1, "Low Sec", "G1"),
            _make_secretariat(2, "High Sec", "G2"),
        ]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        perf_mock_1 = MagicMock()
        perf_mock_1.scalar.return_value = 10

        perf_mock_2 = MagicMock()
        perf_mock_2.scalar.return_value = 50

        mock_db.execute = AsyncMock(side_effect=[sec_mock, perf_mock_1, perf_mock_2])

        result = await service.get_secretariat_rankings("Mangalagiri")
        assert result[0]["secretariat_name"] == "High Sec"
        assert result[0]["value"] == 50
        assert result[1]["value"] == 10

    @pytest.mark.asyncio
    async def test_rankings_respects_limit(self, mock_db, service):
        secs = [_make_secretariat(i, f"Sec{i}", f"G{i}") for i in range(5)]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        perf_mocks = []
        for i in range(5):
            m = MagicMock()
            m.scalar.return_value = i * 10
            perf_mocks.append(m)

        mock_db.execute = AsyncMock(side_effect=[sec_mock] + perf_mocks)

        result = await service.get_secretariat_rankings("Mangalagiri", limit=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rankings_empty_mandal(self, mock_db, service):
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=sec_mock)

        result = await service.get_secretariat_rankings("Empty")
        assert result == []


# ---------------------------------------------------------------------------
# TestSLABreachAlerts
# ---------------------------------------------------------------------------

class TestSLABreachAlerts:
    @pytest.mark.asyncio
    async def test_sla_alerts_returns_overdue_grievances(self, mock_db, service):
        g = _make_grievance(status="open")

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1

        grv_mock = MagicMock()
        grv_mock.scalars.return_value.all.return_value = [g]

        mock_db.execute = AsyncMock(side_effect=[count_mock, grv_mock])

        alerts, total = await service.get_sla_breach_alerts()
        assert total == 1
        assert len(alerts) == 1
        assert alerts[0]["status"] == "open"

    @pytest.mark.asyncio
    async def test_sla_alerts_calculates_hours_overdue(self, mock_db, service):
        deadline = datetime.now(timezone.utc) - timedelta(hours=24)
        g = _make_grievance(status="in_progress", sla_deadline=deadline)

        count_mock = MagicMock()
        count_mock.scalar.return_value = 1

        grv_mock = MagicMock()
        grv_mock.scalars.return_value.all.return_value = [g]

        mock_db.execute = AsyncMock(side_effect=[count_mock, grv_mock])

        alerts, _ = await service.get_sla_breach_alerts()
        # Should be approximately 24 hours overdue
        assert alerts[0]["hours_overdue"] >= 23.9
        assert alerts[0]["hours_overdue"] <= 24.1

    @pytest.mark.asyncio
    async def test_sla_alerts_filters_by_mandal(self, mock_db, service):
        """When mandal is provided, the query should filter by secretariat IDs."""
        count_mock = MagicMock()
        count_mock.scalar.return_value = 0

        grv_mock = MagicMock()
        grv_mock.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[count_mock, grv_mock])

        alerts, total = await service.get_sla_breach_alerts(mandal="Mangalagiri")
        assert total == 0
        assert alerts == []

    @pytest.mark.asyncio
    async def test_sla_alerts_pagination(self, mock_db, service):
        grievances = [_make_grievance(reference_number=f"GRV-{i}") for i in range(3)]

        count_mock = MagicMock()
        count_mock.scalar.return_value = 10  # total is more than returned

        grv_mock = MagicMock()
        grv_mock.scalars.return_value.all.return_value = grievances

        mock_db.execute = AsyncMock(side_effect=[count_mock, grv_mock])

        alerts, total = await service.get_sla_breach_alerts(limit=3, offset=0)
        assert total == 10
        assert len(alerts) == 3


# ---------------------------------------------------------------------------
# TestLowPerforming
# ---------------------------------------------------------------------------

class TestLowPerforming:
    @pytest.mark.asyncio
    async def test_low_performing_below_threshold(self, mock_db, service):
        secs = [_make_secretariat(1, "Bad Sec", "G1")]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        task_mock = MagicMock()
        task_mock.one.return_value = LowPerfRow(total=100, completed=20)

        mock_db.execute = AsyncMock(side_effect=[sec_mock, task_mock])

        result = await service.get_low_performing_secretariats("Guntur", threshold_completion_rate=50.0)
        assert len(result) == 1
        assert result[0]["task_completion_rate"] == 20.0

    @pytest.mark.asyncio
    async def test_low_performing_sorted_by_rate(self, mock_db, service):
        secs = [
            _make_secretariat(1, "Worst", "G1"),
            _make_secretariat(2, "Bad", "G2"),
        ]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        task_mock_1 = MagicMock()
        task_mock_1.one.return_value = LowPerfRow(total=100, completed=30)

        task_mock_2 = MagicMock()
        task_mock_2.one.return_value = LowPerfRow(total=100, completed=10)

        mock_db.execute = AsyncMock(side_effect=[sec_mock, task_mock_1, task_mock_2])

        result = await service.get_low_performing_secretariats("Guntur")
        assert result[0]["task_completion_rate"] < result[1]["task_completion_rate"]
        assert result[0]["secretariat_name"] == "Bad"

    @pytest.mark.asyncio
    async def test_low_performing_100_percent_when_no_tasks(self, mock_db, service):
        """Secretariats with no tasks should have 100% rate (not flagged)."""
        secs = [_make_secretariat(1, "Empty Sec", "G1")]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        task_mock = MagicMock()
        task_mock.one.return_value = LowPerfRow(total=0, completed=0)

        mock_db.execute = AsyncMock(side_effect=[sec_mock, task_mock])

        result = await service.get_low_performing_secretariats("Guntur")
        assert len(result) == 0  # 100% rate is above threshold, not flagged


# ---------------------------------------------------------------------------
# TestEmployeeDetail
# ---------------------------------------------------------------------------

class TestEmployeeDetail:
    @pytest.mark.asyncio
    async def test_employee_detail_returns_full_info(self, mock_db, service):
        emp = _make_employee(1, name_te="రాము", name_en="Ramu")

        emp_mock = MagicMock()
        emp_mock.scalar_one_or_none.return_value = emp

        perf_mock = MagicMock()
        perf_mock.scalar_one_or_none.return_value = None

        open_grv_mock = MagicMock()
        open_grv_mock.scalar.return_value = 3

        pending_mock = MagicMock()
        pending_mock.scalar.return_value = 5

        mock_db.execute = AsyncMock(side_effect=[emp_mock, perf_mock, open_grv_mock, pending_mock])

        result = await service.get_employee_detail(1)
        assert result is not None
        assert result["employee_id"] == 1
        assert result["name_te"] == "రాము"
        assert result["open_grievances"] == 3
        assert result["pending_tasks"] == 5
        assert result["performance"] is None

    @pytest.mark.asyncio
    async def test_employee_detail_not_found(self, mock_db, service):
        emp_mock = MagicMock()
        emp_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=emp_mock)

        result = await service.get_employee_detail(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_employee_detail_with_performance(self, mock_db, service):
        emp = _make_employee(1)

        perf = MagicMock()
        perf.grievances_filed = 10
        perf.grievances_resolved = 8
        perf.tasks_completed = 25
        perf.forms_processed = 50
        perf.total_time_saved_minutes = 120.5

        emp_mock = MagicMock()
        emp_mock.scalar_one_or_none.return_value = emp

        perf_mock = MagicMock()
        perf_mock.scalar_one_or_none.return_value = perf

        open_grv_mock = MagicMock()
        open_grv_mock.scalar.return_value = 0

        pending_mock = MagicMock()
        pending_mock.scalar.return_value = 2

        mock_db.execute = AsyncMock(side_effect=[emp_mock, perf_mock, open_grv_mock, pending_mock])

        result = await service.get_employee_detail(1)
        assert result["performance"] is not None
        assert result["performance"]["grievances_resolved"] == 8
        assert result["performance"]["time_saved_minutes"] == 120.5


# ---------------------------------------------------------------------------
# TestSupervisorAPI — FastAPI TestClient integration
# ---------------------------------------------------------------------------

class TestSupervisorAPI:
    @pytest.fixture
    def mock_db_api(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def app(self, mock_db_api):
        from fastapi import FastAPI
        from app.api.v1.router import api_v1_router
        from app.dependencies import get_db

        test_app = FastAPI()
        test_app.include_router(api_v1_router, prefix="/api/v1")

        async def override_get_db():
            yield mock_db_api

        test_app.dependency_overrides[get_db] = override_get_db
        return test_app

    @pytest.fixture
    def client(self, app):
        return TestClient(app, raise_server_exceptions=False)

    def test_mandal_overview_endpoint(self, client, mock_db_api):
        """GET /api/v1/supervisor/mandal/{name}/overview returns 200."""
        secs = [_make_secretariat(1, "Sec A", "GS001")]
        sec_mock = MagicMock()
        sec_mock.scalars.return_value.all.return_value = secs

        grv_row = Row(total=5, resolved=3, open=1, sla_breached=1)
        grv_mock = MagicMock()
        grv_mock.one.return_value = grv_row

        task_row = TaskRow(total=10, completed=8, pending=2)
        task_mock = MagicMock()
        task_mock.one.return_value = task_row

        emp_mock = MagicMock()
        emp_mock.scalar.return_value = 4

        mock_db_api.execute = AsyncMock(side_effect=[sec_mock, grv_mock, task_mock, emp_mock])

        response = client.get("/api/v1/supervisor/mandal/Mangalagiri/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["mandal"] == "Mangalagiri"
        assert data["grievances"]["total"] == 5

    def test_sla_breaches_endpoint(self, client, mock_db_api):
        """GET /api/v1/supervisor/alerts/sla-breaches returns alerts list."""
        count_mock = MagicMock()
        count_mock.scalar.return_value = 0

        grv_mock = MagicMock()
        grv_mock.scalars.return_value.all.return_value = []

        mock_db_api.execute = AsyncMock(side_effect=[count_mock, grv_mock])

        response = client.get("/api/v1/supervisor/alerts/sla-breaches")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert data["total"] == 0

    def test_employee_detail_endpoint_404(self, client, mock_db_api):
        """GET /api/v1/supervisor/employee/999/detail returns 404 when not found."""
        emp_mock = MagicMock()
        emp_mock.scalar_one_or_none.return_value = None
        mock_db_api.execute = AsyncMock(return_value=emp_mock)

        response = client.get("/api/v1/supervisor/employee/999/detail")
        assert response.status_code == 404
        assert response.json()["detail"] == "Employee not found"
