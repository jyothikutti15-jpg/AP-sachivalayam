from datetime import date, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import BurnoutIndicator, DailyMetric
from app.models.interaction import ChatSession, Message
from app.models.user import Employee, Secretariat
from app.schemas.analytics import BurnoutReportResponse, SecretariatSummaryResponse, TimeSavedResponse

logger = structlog.get_logger()

# Estimated minutes per manual task (for time-saved calculations)
MINUTES_PER_MANUAL_QUERY = 15  # Avg time to look up scheme info manually
MINUTES_PER_MANUAL_FORM = 30  # Avg time to fill a form manually
AVG_EMPLOYEE_HOURLY_COST_INR = 150  # ~₹25k/month / 160 hours


class AnalyticsService:
    """Aggregates metrics for burnout reduction reporting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_secretariat_summary(
        self,
        secretariat_id: int,
        start_date: date,
        end_date: date,
    ) -> SecretariatSummaryResponse:
        """Get usage summary for a specific secretariat."""
        # Get secretariat info
        sec_result = await self.db.execute(
            select(Secretariat).where(Secretariat.id == secretariat_id)
        )
        secretariat = sec_result.scalar_one_or_none()
        if not secretariat:
            return SecretariatSummaryResponse(
                secretariat_id=secretariat_id,
                secretariat_name="Unknown",
                period_start=start_date,
                period_end=end_date,
            )

        # Aggregate daily metrics for all employees in this secretariat
        result = await self.db.execute(
            select(
                func.sum(DailyMetric.queries_handled),
                func.sum(DailyMetric.forms_auto_filled),
                func.sum(DailyMetric.time_saved_minutes),
                func.count(func.distinct(DailyMetric.employee_id)),
            )
            .join(Employee, Employee.id == DailyMetric.employee_id)
            .where(Employee.secretariat_id == secretariat_id)
            .where(DailyMetric.date >= start_date)
            .where(DailyMetric.date <= end_date)
        )
        row = result.one()

        return SecretariatSummaryResponse(
            secretariat_id=secretariat_id,
            secretariat_name=secretariat.name_en,
            period_start=start_date,
            period_end=end_date,
            total_queries=row[0] or 0,
            total_forms_filled=row[1] or 0,
            total_time_saved_hours=float(row[2] or 0) / 60.0,
            active_employees=row[3] or 0,
        )

    async def get_burnout_report(
        self,
        week_start: date,
        district: str | None = None,
    ) -> list[BurnoutReportResponse]:
        """Get burnout reduction metrics per secretariat."""
        query = (
            select(BurnoutIndicator, Secretariat)
            .join(Secretariat, Secretariat.id == BurnoutIndicator.secretariat_id)
            .where(BurnoutIndicator.week_start == week_start)
        )
        if district:
            query = query.where(Secretariat.district == district)

        result = await self.db.execute(query)
        rows = result.all()

        reports = []
        for indicator, secretariat in rows:
            hours_reduction = None
            if indicator.avg_daily_hours_before and indicator.avg_daily_hours_with_copilot:
                hours_reduction = (
                    (float(indicator.avg_daily_hours_before) - float(indicator.avg_daily_hours_with_copilot))
                    / float(indicator.avg_daily_hours_before)
                    * 100
                )

            reports.append(BurnoutReportResponse(
                secretariat_id=secretariat.id,
                secretariat_name=secretariat.name_en,
                week_start=week_start,
                avg_daily_hours_before=float(indicator.avg_daily_hours_before) if indicator.avg_daily_hours_before else None,
                avg_daily_hours_with_copilot=float(indicator.avg_daily_hours_with_copilot) if indicator.avg_daily_hours_with_copilot else None,
                hours_reduction_pct=hours_reduction,
                repetitive_queries_automated=indicator.repetitive_queries_automated,
                employee_satisfaction_score=float(indicator.employee_satisfaction_score) if indicator.employee_satisfaction_score else None,
            ))

        return reports

    async def get_time_saved(
        self,
        start_date: date,
        end_date: date,
        district: str | None = None,
    ) -> TimeSavedResponse:
        """Calculate total time saved across all employees."""
        query = select(
            func.sum(DailyMetric.queries_handled),
            func.sum(DailyMetric.forms_auto_filled),
            func.sum(DailyMetric.time_saved_minutes),
            func.count(func.distinct(DailyMetric.employee_id)),
        ).join(Employee, Employee.id == DailyMetric.employee_id)

        if district:
            query = query.join(Secretariat, Secretariat.id == Employee.secretariat_id).where(
                Secretariat.district == district
            )

        query = query.where(DailyMetric.date >= start_date).where(DailyMetric.date <= end_date)

        result = await self.db.execute(query)
        row = result.one()

        total_queries = row[0] or 0
        total_forms = row[1] or 0
        total_time_saved_minutes = float(row[2] or 0)

        # If no tracked time, estimate from activities
        if total_time_saved_minutes == 0:
            total_time_saved_minutes = (
                total_queries * MINUTES_PER_MANUAL_QUERY
                + total_forms * MINUTES_PER_MANUAL_FORM
            )

        total_hours = total_time_saved_minutes / 60.0
        days_in_period = (end_date - start_date).days or 1

        # Project annual savings
        annual_factor = 365.0 / days_in_period
        projected_annual_hours = total_hours * annual_factor
        projected_cost_savings = projected_annual_hours * AVG_EMPLOYEE_HOURLY_COST_INR

        return TimeSavedResponse(
            period_start=start_date,
            period_end=end_date,
            total_time_saved_hours=total_hours,
            total_forms_auto_filled=total_forms,
            total_queries_handled=total_queries,
            total_employees_served=row[3] or 0,
            projected_annual_hours_saved=projected_annual_hours,
            projected_cost_savings_inr=projected_cost_savings,
        )

    async def export_report(self, start_date: date, end_date: date, format: str) -> str:
        """Export analytics data to file. Returns file path."""
        import csv
        import tempfile

        time_saved = await self.get_time_saved(start_date, end_date)

        if format == "csv":
            filepath = tempfile.mktemp(suffix=".csv")
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Metric", "Value"])
                writer.writerow(["Period", f"{start_date} to {end_date}"])
                writer.writerow(["Total Queries Handled", time_saved.total_queries_handled])
                writer.writerow(["Total Forms Auto-Filled", time_saved.total_forms_auto_filled])
                writer.writerow(["Total Time Saved (hours)", f"{time_saved.total_time_saved_hours:.1f}"])
                writer.writerow(["Employees Served", time_saved.total_employees_served])
                writer.writerow(["Projected Annual Hours Saved", f"{time_saved.projected_annual_hours_saved:.0f}"])
                writer.writerow(["Projected Cost Savings (INR)", f"₹{time_saved.projected_cost_savings_inr:,.0f}"])
            return filepath

        # PDF export (TODO: implement with WeasyPrint)
        return await self._export_pdf(time_saved, start_date, end_date)

    async def get_district_summary(self, district: str, start_date: date, end_date: date) -> dict:
        """Get aggregated metrics for an entire district."""
        result = await self.db.execute(
            select(
                func.count(func.distinct(Secretariat.id)).label("secretariats"),
                func.count(func.distinct(DailyMetric.employee_id)).label("employees"),
                func.sum(DailyMetric.queries_handled).label("queries"),
                func.sum(DailyMetric.forms_auto_filled).label("forms"),
                func.sum(DailyMetric.time_saved_minutes).label("time_saved"),
            )
            .join(Employee, Employee.id == DailyMetric.employee_id)
            .join(Secretariat, Secretariat.id == Employee.secretariat_id)
            .where(Secretariat.district == district)
            .where(DailyMetric.date >= start_date)
            .where(DailyMetric.date <= end_date)
        )
        row = result.one()

        return {
            "district": district,
            "period": f"{start_date} to {end_date}",
            "secretariats_active": row.secretariats or 0,
            "employees_active": row.employees or 0,
            "total_queries": row.queries or 0,
            "total_forms": row.forms or 0,
            "time_saved_hours": float(row.time_saved or 0) / 60.0,
        }

    async def get_top_schemes_queried(
        self, start_date: date, end_date: date, limit: int = 10
    ) -> list[dict]:
        """Get most frequently queried schemes."""
        result = await self.db.execute(
            select(
                Message.detected_intent,
                Message.content_text,
                func.count(Message.id).label("count"),
            )
            .join(ChatSession)
            .where(func.date(ChatSession.started_at) >= start_date)
            .where(func.date(ChatSession.started_at) <= end_date)
            .where(Message.direction == "in")
            .where(Message.detected_intent == "scheme_query")
            .group_by(Message.detected_intent, Message.content_text)
            .order_by(func.count(Message.id).desc())
            .limit(limit)
        )
        return [{"query": row[1][:50], "count": row[2]} for row in result.all()]

    async def record_interaction(
        self, employee_id: int, interaction_type: str, time_saved_minutes: float = 0
    ) -> None:
        """Record a single interaction metric. Called after each conversation."""
        today = date.today()

        from sqlalchemy.dialects.postgresql import insert

        if interaction_type == "query":
            stmt = insert(DailyMetric).values(
                employee_id=employee_id,
                date=today,
                queries_handled=1,
                time_saved_minutes=MINUTES_PER_MANUAL_QUERY,
                session_count=1,
            ).on_conflict_do_update(
                index_elements=["employee_id", "date"],
                set_={
                    "queries_handled": DailyMetric.queries_handled + 1,
                    "time_saved_minutes": DailyMetric.time_saved_minutes + MINUTES_PER_MANUAL_QUERY,
                },
            )
        elif interaction_type == "form":
            stmt = insert(DailyMetric).values(
                employee_id=employee_id,
                date=today,
                forms_auto_filled=1,
                time_saved_minutes=MINUTES_PER_MANUAL_FORM,
                session_count=1,
            ).on_conflict_do_update(
                index_elements=["employee_id", "date"],
                set_={
                    "forms_auto_filled": DailyMetric.forms_auto_filled + 1,
                    "time_saved_minutes": DailyMetric.time_saved_minutes + MINUTES_PER_MANUAL_FORM,
                },
            )
        else:
            return

        await self.db.execute(stmt)

    async def _export_pdf(self, data: TimeSavedResponse, start_date: date, end_date: date) -> str:
        """Generate PDF analytics report with AP government styling."""
        import tempfile

        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;700&display=swap');
    body {{ font-family: 'Noto Sans Telugu', sans-serif; padding: 30px; }}
    .header {{ text-align: center; border-bottom: 2px solid #1a5276; padding-bottom: 10px; margin-bottom: 20px; }}
    .header h1 {{ color: #1a5276; font-size: 18pt; }}
    .header h2 {{ color: #666; font-size: 12pt; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
    td, th {{ padding: 8px 12px; border: 1px solid #ddd; text-align: left; }}
    th {{ background: #1a5276; color: white; }}
    .highlight {{ font-size: 24pt; color: #27ae60; font-weight: 700; text-align: center; }}
    .metric-box {{ display: inline-block; width: 30%; text-align: center; margin: 10px; padding: 15px; background: #eaf2f8; border-radius: 8px; }}
</style>
</head><body>
    <div class="header">
        <h1>AP సచివాలయం AI Copilot — Analytics Report</h1>
        <h2>Period: {start_date} to {end_date}</h2>
    </div>

    <div style="text-align: center; margin: 20px 0;">
        <div class="metric-box">
            <div class="highlight">{data.total_time_saved_hours:.0f}</div>
            <div>Hours Saved</div>
        </div>
        <div class="metric-box">
            <div class="highlight">{data.total_queries_handled}</div>
            <div>Queries Handled</div>
        </div>
        <div class="metric-box">
            <div class="highlight">{data.total_forms_auto_filled}</div>
            <div>Forms Auto-Filled</div>
        </div>
    </div>

    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Total Employees Served</td><td>{data.total_employees_served}</td></tr>
        <tr><td>Total Queries Handled</td><td>{data.total_queries_handled}</td></tr>
        <tr><td>Total Forms Auto-Filled</td><td>{data.total_forms_auto_filled}</td></tr>
        <tr><td>Total Time Saved</td><td>{data.total_time_saved_hours:.1f} hours</td></tr>
        <tr><td>Projected Annual Hours Saved</td><td>{data.projected_annual_hours_saved:,.0f} hours</td></tr>
        <tr><td>Projected Annual Cost Savings</td><td>₹{data.projected_cost_savings_inr:,.0f}</td></tr>
    </table>

    <div style="margin-top: 30px; text-align: center; color: #888; font-size: 9pt;">
        Generated by AP Sachivalayam AI Copilot | {date.today()}
    </div>
</body></html>"""

        try:
            from weasyprint import HTML
            filepath = tempfile.mktemp(suffix=".pdf")
            HTML(string=html).write_pdf(filepath)
            return filepath
        except ImportError:
            filepath = tempfile.mktemp(suffix=".html")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            return filepath
