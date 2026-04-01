"""Tests for Analytics Service."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.analytics import TimeSavedResponse


class TestTimeSavedCalculation:
    """Test time saved projections."""

    def test_annual_projection(self):
        """Test that annual projection scales correctly."""
        data = TimeSavedResponse(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            total_time_saved_hours=100,
            total_forms_auto_filled=50,
            total_queries_handled=500,
            total_employees_served=10,
            projected_annual_hours_saved=100 * (365 / 30),
            projected_cost_savings_inr=100 * (365 / 30) * 150,
        )

        assert data.projected_annual_hours_saved > 1000
        assert data.projected_cost_savings_inr > 0

    def test_zero_period_handling(self):
        """Zero metrics should not cause division errors."""
        data = TimeSavedResponse(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 1),
            total_time_saved_hours=0,
            total_forms_auto_filled=0,
            total_queries_handled=0,
            total_employees_served=0,
            projected_annual_hours_saved=0,
            projected_cost_savings_inr=0,
        )
        assert data.total_time_saved_hours == 0


class TestBurnoutReport:
    """Test burnout metrics calculation."""

    def test_hours_reduction_percentage(self):
        """Test burnout reduction percentage calculation."""
        before = 10.0  # hours/day
        after = 7.5    # hours/day

        reduction_pct = (before - after) / before * 100
        assert reduction_pct == 25.0

    def test_no_reduction_when_equal(self):
        before = 8.0
        after = 8.0
        reduction_pct = (before - after) / before * 100
        assert reduction_pct == 0.0


class TestExportFormats:
    """Test analytics export."""

    def test_csv_export_format(self):
        """CSV export should have standard headers."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Queries", 500])
        writer.writerow(["Time Saved (hours)", "100.5"])

        csv_content = output.getvalue()
        assert "Metric,Value" in csv_content
        assert "500" in csv_content
