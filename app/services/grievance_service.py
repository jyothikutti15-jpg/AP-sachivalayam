"""
Grievance Resolution Service — Handles citizen complaints with AI-powered
category detection, department routing, SLA tracking, and escalation.

72-hour resolution SLA per AP government mandate.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grievance import (
    GRIEVANCE_CATEGORIES,
    Grievance,
    GrievanceComment,
)
from app.models.user import Employee
from app.schemas.grievance import (
    GrievanceAISuggestResponse,
    GrievanceCommentResponse,
    GrievanceCreateRequest,
    GrievanceResponse,
    GrievanceUpdateRequest,
)
from app.services.llm_service import LLMRouter

logger = structlog.get_logger()

# SLA: 72 hours for resolution
SLA_HOURS = 72

# Priority-based SLA multipliers
PRIORITY_SLA = {
    "urgent": 24,
    "high": 48,
    "medium": 72,
    "low": 120,
}

GRIEVANCE_AI_PROMPT = """You are an AP Sachivalayam Grievance Resolution Assistant.
Analyze the citizen grievance below and provide structured guidance.

Respond in JSON:
{{
    "suggested_category": "one of: agriculture, health, education, welfare, revenue, water_supply, electricity, road_transport, other",
    "suggested_department": "AP government department name",
    "suggested_priority": "low/medium/high/urgent",
    "escalation_path_te": "Telugu text: which officials to escalate to if unresolved",
    "required_evidence_te": ["list of documents/evidence needed in Telugu"],
    "resolution_suggestion_te": "Telugu text: suggested resolution steps"
}}

GRIEVANCE:
Category: {category}
Subject: {subject}
Description: {description}
"""


class GrievanceService:
    """Manages grievance lifecycle: filing, routing, tracking, escalation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMRouter()

    async def file_grievance(
        self,
        request: GrievanceCreateRequest,
        employee_id: int,
        secretariat_id: int | None = None,
    ) -> GrievanceResponse:
        """File a new citizen grievance."""
        # Generate reference number
        ref_number = await self._generate_reference_number()

        # Auto-detect department from category if not provided
        department = request.department
        if not department:
            cat_info = GRIEVANCE_CATEGORIES.get(request.category, {})
            department = cat_info.get("department", "General Administration")

        # Calculate SLA deadline based on priority
        sla_hours = PRIORITY_SLA.get(request.priority, SLA_HOURS)
        sla_deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

        grievance = Grievance(
            reference_number=ref_number,
            filed_by_employee_id=employee_id,
            secretariat_id=secretariat_id,
            citizen_name=request.citizen_name,
            citizen_phone=request.citizen_phone,
            category=request.category,
            subcategory=request.subcategory,
            department=department,
            subject_te=request.subject_te,
            description_te=request.description_te,
            description_en=request.description_en,
            priority=request.priority,
            sla_deadline=sla_deadline,
            attachment_urls={"urls": request.attachment_urls} if request.attachment_urls else None,
        )

        self.db.add(grievance)
        await self.db.flush()

        logger.info(
            "Grievance filed",
            reference=ref_number,
            category=request.category,
            department=department,
            priority=request.priority,
        )

        return await self._to_response(grievance)

    async def get_grievance(self, grievance_id: uuid.UUID) -> GrievanceResponse | None:
        """Get a single grievance by ID."""
        result = await self.db.execute(
            select(Grievance).where(Grievance.id == grievance_id)
        )
        grievance = result.scalar_one_or_none()
        if not grievance:
            return None
        return await self._to_response(grievance)

    async def get_by_reference(self, reference_number: str) -> GrievanceResponse | None:
        """Get a grievance by reference number."""
        result = await self.db.execute(
            select(Grievance).where(Grievance.reference_number == reference_number)
        )
        grievance = result.scalar_one_or_none()
        if not grievance:
            return None
        return await self._to_response(grievance)

    async def list_grievances(
        self,
        employee_id: int | None = None,
        secretariat_id: int | None = None,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[GrievanceResponse], int]:
        """List grievances with filters."""
        query = select(Grievance)

        if employee_id:
            query = query.where(Grievance.filed_by_employee_id == employee_id)
        if secretariat_id:
            query = query.where(Grievance.secretariat_id == secretariat_id)
        if status:
            query = query.where(Grievance.status == status)
        if category:
            query = query.where(Grievance.category == category)
        if priority:
            query = query.where(Grievance.priority == priority)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate and order
        query = (
            query.order_by(Grievance.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        grievances = result.scalars().all()

        responses = []
        for g in grievances:
            responses.append(await self._to_response(g))

        return responses, total

    async def update_grievance(
        self,
        grievance_id: uuid.UUID,
        update: GrievanceUpdateRequest,
        employee_id: int,
    ) -> GrievanceResponse | None:
        """Update grievance status, assignment, or resolution."""
        result = await self.db.execute(
            select(Grievance).where(Grievance.id == grievance_id)
        )
        grievance = result.scalar_one_or_none()
        if not grievance:
            return None

        now = datetime.now(timezone.utc)

        if update.status:
            old_status = grievance.status
            grievance.status = update.status

            if update.status == "acknowledged" and not grievance.acknowledged_at:
                grievance.acknowledged_at = now
            elif update.status == "resolved" and not grievance.resolved_at:
                grievance.resolved_at = now
            elif update.status == "closed":
                grievance.closed_at = now

            # Log status change as comment
            comment = GrievanceComment(
                grievance_id=grievance.id,
                employee_id=employee_id,
                comment_text=f"Status changed: {old_status} -> {update.status}",
                comment_type="status_change",
            )
            self.db.add(comment)

        if update.priority:
            grievance.priority = update.priority
            # Recalculate SLA if priority changed and not yet resolved
            if grievance.status not in ("resolved", "closed"):
                sla_hours = PRIORITY_SLA.get(update.priority, SLA_HOURS)
                grievance.sla_deadline = grievance.created_at + timedelta(hours=sla_hours)

        if update.assigned_to_employee_id:
            grievance.assigned_to_employee_id = update.assigned_to_employee_id

        if update.resolution_notes_te:
            grievance.resolution_notes_te = update.resolution_notes_te
        if update.resolution_notes_en:
            grievance.resolution_notes_en = update.resolution_notes_en
        if update.citizen_satisfaction is not None:
            grievance.citizen_satisfaction = update.citizen_satisfaction

        await self.db.flush()
        logger.info("Grievance updated", id=str(grievance_id), status=grievance.status)

        return await self._to_response(grievance)

    async def add_comment(
        self,
        grievance_id: uuid.UUID,
        employee_id: int,
        comment_text: str,
        comment_type: str = "note",
    ) -> GrievanceCommentResponse:
        """Add a comment to a grievance."""
        comment = GrievanceComment(
            grievance_id=grievance_id,
            employee_id=employee_id,
            comment_text=comment_text,
            comment_type=comment_type,
        )
        self.db.add(comment)
        await self.db.flush()

        return GrievanceCommentResponse(
            id=comment.id,
            employee_id=comment.employee_id,
            comment_text=comment.comment_text,
            comment_type=comment.comment_type,
            created_at=comment.created_at,
        )

    async def ai_suggest(
        self,
        category: str,
        subject: str,
        description: str,
    ) -> GrievanceAISuggestResponse:
        """Use AI to suggest category, priority, escalation path, and evidence needed."""
        prompt = GRIEVANCE_AI_PROMPT.format(
            category=category,
            subject=subject,
            description=description,
        )

        try:
            response = await self.llm.call_claude_structured(
                prompt=f"Analyze this grievance:\n{description}",
                system_prompt=prompt,
            )
            data = json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("AI grievance suggestion failed", error=str(e))
            cat_info = GRIEVANCE_CATEGORIES.get(category, GRIEVANCE_CATEGORIES["other"])
            data = {
                "suggested_category": category,
                "suggested_department": cat_info.get("department", "General Administration"),
                "suggested_priority": "medium",
                "escalation_path_te": "సచివాలయం → మండల అధికారి → జిల్లా కలెక్టర్",
                "required_evidence_te": ["దరఖాస్తు కాపీ", "గుర్తింపు పత్రం"],
                "resolution_suggestion_te": "సంబంధిత శాఖకు నివేదించండి.",
            }

        return GrievanceAISuggestResponse(
            suggested_category=data.get("suggested_category", category),
            suggested_department=data.get("suggested_department", "General Administration"),
            suggested_priority=data.get("suggested_priority", "medium"),
            escalation_path_te=data.get("escalation_path_te", ""),
            required_evidence_te=data.get("required_evidence_te", []),
            similar_grievances=[],
            resolution_suggestion_te=data.get("resolution_suggestion_te", ""),
        )

    async def check_and_escalate_overdue(self) -> int:
        """Check for SLA-breached grievances and auto-escalate. Run via Celery."""
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(Grievance)
            .where(Grievance.status.in_(["open", "acknowledged", "in_progress"]))
            .where(Grievance.sla_deadline < now)
            .where(Grievance.is_sla_breached.is_(False))
        )
        overdue = result.scalars().all()

        escalated = 0
        for grievance in overdue:
            grievance.is_sla_breached = True

            if grievance.escalation_level < 3:
                grievance.escalation_level += 1
                grievance.status = "escalated" if grievance.status != "in_progress" else grievance.status

                comment = GrievanceComment(
                    grievance_id=grievance.id,
                    employee_id=grievance.filed_by_employee_id,
                    comment_text=(
                        f"SLA breached. Auto-escalated to level {grievance.escalation_level}. "
                        f"Deadline was {grievance.sla_deadline.isoformat()}"
                    ),
                    comment_type="escalation",
                )
                self.db.add(comment)
                escalated += 1

                logger.warning(
                    "Grievance SLA breached",
                    reference=grievance.reference_number,
                    level=grievance.escalation_level,
                )

        if escalated:
            await self.db.flush()
        logger.info("SLA check complete", overdue=len(overdue), escalated=escalated)
        return escalated

    async def get_grievance_stats(
        self, secretariat_id: int | None = None
    ) -> dict:
        """Get grievance statistics for dashboard."""
        base = select(Grievance)
        if secretariat_id:
            base = base.where(Grievance.secretariat_id == secretariat_id)

        # Total by status
        status_query = (
            select(Grievance.status, func.count())
            .select_from(base.subquery())
            .group_by(Grievance.status)
        )
        # Simplified: count by status directly
        statuses = {}
        for status in ["open", "acknowledged", "in_progress", "escalated", "resolved", "closed"]:
            q = select(func.count()).where(Grievance.status == status)
            if secretariat_id:
                q = q.where(Grievance.secretariat_id == secretariat_id)
            count = (await self.db.execute(q)).scalar() or 0
            statuses[status] = count

        # SLA breach count
        breached_q = select(func.count()).where(Grievance.is_sla_breached.is_(True))
        if secretariat_id:
            breached_q = breached_q.where(Grievance.secretariat_id == secretariat_id)
        sla_breached = (await self.db.execute(breached_q)).scalar() or 0

        # Average resolution time (for resolved/closed)
        avg_q = select(
            func.avg(
                func.extract("epoch", Grievance.resolved_at - Grievance.created_at) / 3600
            )
        ).where(Grievance.resolved_at.isnot(None))
        if secretariat_id:
            avg_q = avg_q.where(Grievance.secretariat_id == secretariat_id)
        avg_hours = (await self.db.execute(avg_q)).scalar()

        return {
            "by_status": statuses,
            "total": sum(statuses.values()),
            "sla_breached": sla_breached,
            "avg_resolution_hours": round(avg_hours, 1) if avg_hours else None,
        }

    async def _generate_reference_number(self) -> str:
        """Generate a unique grievance reference number."""
        now = datetime.now(timezone.utc)
        year = now.year

        count_result = await self.db.execute(
            select(func.count())
            .where(Grievance.reference_number.like(f"GRV-{year}-%"))
        )
        count = (count_result.scalar() or 0) + 1

        return f"GRV-{year}-{count:04d}"

    async def _to_response(self, grievance: Grievance) -> GrievanceResponse:
        """Convert Grievance model to response schema."""
        # Fetch comments
        comment_result = await self.db.execute(
            select(GrievanceComment)
            .where(GrievanceComment.grievance_id == grievance.id)
            .order_by(GrievanceComment.created_at)
        )
        comments = comment_result.scalars().all()

        return GrievanceResponse(
            id=grievance.id,
            reference_number=grievance.reference_number,
            citizen_name=grievance.citizen_name,
            category=grievance.category,
            department=grievance.department,
            subject_te=grievance.subject_te,
            description_te=grievance.description_te,
            status=grievance.status,
            priority=grievance.priority,
            escalation_level=grievance.escalation_level,
            sla_deadline=grievance.sla_deadline,
            acknowledged_at=grievance.acknowledged_at,
            resolved_at=grievance.resolved_at,
            is_sla_breached=grievance.is_sla_breached,
            resolution_notes_te=grievance.resolution_notes_te,
            created_at=grievance.created_at,
            updated_at=grievance.updated_at,
            comments=[
                GrievanceCommentResponse(
                    id=c.id,
                    employee_id=c.employee_id,
                    comment_text=c.comment_text,
                    comment_type=c.comment_type,
                    created_at=c.created_at,
                )
                for c in comments
            ],
        )
