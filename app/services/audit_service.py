"""
Audit Service — Logs all actions for government compliance.
"""
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = structlog.get_logger()


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        employee_id: int | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> AuditLog:
        """Log an action to the audit trail."""
        log = AuditLog(
            employee_id=employee_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def get_audit_logs(
        self,
        resource_type: str | None = None,
        resource_id: str | None = None,
        employee_id: int | None = None,
        action: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        """Query audit logs with filters."""
        query = select(AuditLog)

        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if employee_id:
            query = query.where(AuditLog.employee_id == employee_id)
        if action:
            query = query.where(AuditLog.action == action)
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        query = (
            query.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        logs = result.scalars().all()

        return logs, total

    async def get_employee_activity(
        self, employee_id: int, days: int = 30
    ) -> dict:
        """Get employee activity summary for the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Count by action type
        result = await self.db.execute(
            select(AuditLog.action, func.count())
            .where(AuditLog.employee_id == employee_id)
            .where(AuditLog.created_at >= cutoff)
            .group_by(AuditLog.action)
        )
        action_counts = {row[0]: row[1] for row in result.all()}

        # Count by resource type
        result2 = await self.db.execute(
            select(AuditLog.resource_type, func.count())
            .where(AuditLog.employee_id == employee_id)
            .where(AuditLog.created_at >= cutoff)
            .group_by(AuditLog.resource_type)
        )
        resource_counts = {row[0]: row[1] for row in result2.all()}

        # Total actions
        total = sum(action_counts.values())

        return {
            "employee_id": employee_id,
            "period_days": days,
            "total_actions": total,
            "by_action": action_counts,
            "by_resource": resource_counts,
        }
