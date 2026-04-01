"""
Task Prioritization Service — AI-powered daily task management.

Reads pending work queue across 34 departments and tells employees what to do first,
reducing decision-overload burnout.
"""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import DailyPlan, Task
from app.models.user import Employee
from app.schemas.task import (
    DailyPlanResponse,
    PrioritizedTask,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
    WorkloadSummaryResponse,
)
from app.services.llm_service import LLMRouter

logger = structlog.get_logger()

PRIORITIZATION_PROMPT = """You are an AI task prioritizer for AP Sachivalayam employees.
Given the employee's pending tasks, create an optimal daily plan that minimizes burnout.

RULES:
- Urgent/high priority tasks come first
- Overdue tasks get highest rank
- Group tasks by department when possible to reduce context switching
- Citizen-facing tasks (scheme_processing, citizen_service) take priority over internal tasks
- Keep total estimated time under 8 hours (480 minutes)
- Respond in Telugu for reason_te

Respond in JSON:
{{
    "task_order": [
        {{"task_id": "uuid", "rank": 1, "reason_te": "Telugu reason for this priority"}},
        ...
    ],
    "summary_te": "Telugu: brief summary of today's plan",
    "summary_en": "English: brief summary of today's plan"
}}

EMPLOYEE: {employee_name}, {designation}, {department}
TODAY: {today}

TASKS:
{tasks_json}
"""


class TaskService:
    """Manages tasks and AI-powered daily prioritization."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMRouter()

    async def create_task(
        self,
        request: TaskCreateRequest,
        employee_id: int,
        secretariat_id: int | None = None,
    ) -> TaskResponse:
        """Create a new task for an employee."""
        task = Task(
            employee_id=employee_id,
            secretariat_id=secretariat_id,
            title_te=request.title_te,
            title_en=request.title_en,
            description_te=request.description_te,
            department=request.department,
            category=request.category,
            priority=request.priority,
            priority_score=self._compute_base_priority_score(request.priority, request.due_date),
            due_date=request.due_date,
            estimated_minutes=request.estimated_minutes,
            source=request.source,
            source_reference_id=request.source_reference_id,
            is_recurring=request.is_recurring,
            recurrence_rule=request.recurrence_rule,
        )

        self.db.add(task)
        await self.db.flush()

        logger.info("Task created", task_id=str(task.id), department=request.department)
        return self._to_response(task)

    async def get_task(self, task_id: uuid.UUID) -> TaskResponse | None:
        """Get a single task."""
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return None
        return self._to_response(task)

    async def list_tasks(
        self,
        employee_id: int,
        status: str | None = None,
        department: str | None = None,
        due_date: date | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[TaskResponse], int]:
        """List tasks for an employee with filters."""
        query = select(Task).where(Task.employee_id == employee_id)

        if status:
            query = query.where(Task.status == status)
        if department:
            query = query.where(Task.department == department)
        if due_date:
            query = query.where(Task.due_date == due_date)

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        query = (
            query.order_by(Task.priority_score.desc(), Task.due_date.asc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return [self._to_response(t) for t in tasks], total

    async def update_task(
        self,
        task_id: uuid.UUID,
        update_req: TaskUpdateRequest,
        employee_id: int,
    ) -> TaskResponse | None:
        """Update a task's status or details."""
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return None

        now = datetime.now(timezone.utc)

        if update_req.status:
            task.status = update_req.status
            if update_req.status == "in_progress" and not task.started_at:
                task.started_at = now
            elif update_req.status == "completed":
                task.completed_at = now

        if update_req.priority:
            task.priority = update_req.priority
            task.priority_score = self._compute_base_priority_score(
                update_req.priority, task.due_date
            )

        if update_req.actual_minutes is not None:
            task.actual_minutes = update_req.actual_minutes

        if update_req.title_te:
            task.title_te = update_req.title_te

        if update_req.due_date:
            task.due_date = update_req.due_date

        await self.db.flush()
        logger.info("Task updated", task_id=str(task_id), status=task.status)
        return self._to_response(task)

    async def generate_daily_plan(
        self,
        employee_id: int,
        plan_date: date | None = None,
    ) -> DailyPlanResponse:
        """Generate AI-powered daily task prioritization plan."""
        today = plan_date or date.today()

        # Check if plan already exists
        existing = await self.db.execute(
            select(DailyPlan)
            .where(DailyPlan.employee_id == employee_id)
            .where(DailyPlan.plan_date == today)
        )
        existing_plan = existing.scalar_one_or_none()

        # Get employee info
        emp_result = await self.db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        employee = emp_result.scalar_one_or_none()

        # Get pending + in_progress tasks
        task_result = await self.db.execute(
            select(Task)
            .where(Task.employee_id == employee_id)
            .where(Task.status.in_(["pending", "in_progress"]))
            .where(
                (Task.due_date.is_(None))
                | (Task.due_date <= today + timedelta(days=7))
            )
            .order_by(Task.priority_score.desc())
            .limit(30)
        )
        tasks = list(task_result.scalars().all())

        if not tasks:
            return DailyPlanResponse(
                plan_date=today,
                tasks=[],
                total_estimated_minutes=0,
                ai_summary_te="ఈ రోజు pending tasks లేవు! 🎉",
                ai_summary_en="No pending tasks for today!",
            )

        # Mark overdue tasks
        for task in tasks:
            if task.due_date and task.due_date < today and task.status == "pending":
                task.status = "overdue"
                task.priority_score = min(task.priority_score + 20, 100)

        # Build task list for AI
        tasks_for_ai = []
        for t in tasks:
            tasks_for_ai.append({
                "task_id": str(t.id),
                "title_te": t.title_te,
                "department": t.department,
                "category": t.category,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "estimated_minutes": t.estimated_minutes,
                "status": t.status,
                "is_overdue": t.due_date is not None and t.due_date < today,
            })

        # Call Claude for prioritization
        try:
            prompt = PRIORITIZATION_PROMPT.format(
                employee_name=employee.name_te if employee else "Unknown",
                designation=employee.designation if employee else "Unknown",
                department=employee.department if employee else "Unknown",
                today=today.isoformat(),
                tasks_json=json.dumps(tasks_for_ai, ensure_ascii=False, indent=2),
            )

            response = await self.llm.call_claude_structured(
                prompt=f"Prioritize these {len(tasks)} tasks for today.",
                system_prompt=prompt,
            )
            ai_plan = json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("AI prioritization failed, using rule-based", error=str(e))
            ai_plan = self._rule_based_prioritization(tasks, today)

        # Build task order with AI reasons
        task_map = {str(t.id): t for t in tasks}
        prioritized_tasks = []
        total_minutes = 0

        for item in ai_plan.get("task_order", []):
            tid = item.get("task_id")
            task = task_map.get(tid)
            if not task:
                continue

            # Update priority score based on AI ranking
            rank = item.get("rank", len(prioritized_tasks) + 1)
            task.priority_score = max(100 - (rank - 1) * 5, 10)
            task.ai_priority_reason_te = item.get("reason_te", "")
            task.is_ai_suggested = True

            prioritized_tasks.append(PrioritizedTask(
                task_id=task.id,
                rank=rank,
                title_te=task.title_te,
                department=task.department,
                priority=task.priority,
                priority_score=task.priority_score,
                due_date=task.due_date,
                estimated_minutes=task.estimated_minutes,
                status=task.status,
                reason_te=item.get("reason_te"),
            ))
            total_minutes += task.estimated_minutes

        # Save daily plan
        plan_data = {
            "task_order": ai_plan.get("task_order", []),
        }

        if existing_plan:
            existing_plan.task_order = plan_data
            existing_plan.total_estimated_minutes = total_minutes
            existing_plan.ai_summary_te = ai_plan.get("summary_te")
            existing_plan.ai_summary_en = ai_plan.get("summary_en")
        else:
            plan = DailyPlan(
                employee_id=employee_id,
                plan_date=today,
                task_order=plan_data,
                total_estimated_minutes=total_minutes,
                ai_summary_te=ai_plan.get("summary_te"),
                ai_summary_en=ai_plan.get("summary_en"),
            )
            self.db.add(plan)

        await self.db.flush()

        return DailyPlanResponse(
            plan_date=today,
            tasks=prioritized_tasks,
            total_estimated_minutes=total_minutes,
            ai_summary_te=ai_plan.get("summary_te"),
            ai_summary_en=ai_plan.get("summary_en"),
        )

    async def get_workload_summary(
        self,
        employee_id: int,
        summary_date: date | None = None,
    ) -> WorkloadSummaryResponse:
        """Get workload summary for an employee."""
        today = summary_date or date.today()

        # Count by status
        base = select(Task).where(Task.employee_id == employee_id)

        total = (await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar() or 0

        completed = (await self.db.execute(
            select(func.count()).where(
                Task.employee_id == employee_id,
                Task.status == "completed",
                Task.completed_at >= datetime.combine(today, datetime.min.time()),
            )
        )).scalar() or 0

        overdue = (await self.db.execute(
            select(func.count()).where(
                Task.employee_id == employee_id,
                Task.status.in_(["pending", "overdue"]),
                Task.due_date < today,
            )
        )).scalar() or 0

        pending = (await self.db.execute(
            select(func.count()).where(
                Task.employee_id == employee_id,
                Task.status == "pending",
            )
        )).scalar() or 0

        in_progress = (await self.db.execute(
            select(func.count()).where(
                Task.employee_id == employee_id,
                Task.status == "in_progress",
            )
        )).scalar() or 0

        # Estimated and actual minutes
        est_minutes = (await self.db.execute(
            select(func.sum(Task.estimated_minutes)).where(
                Task.employee_id == employee_id,
                Task.status.in_(["pending", "in_progress"]),
            )
        )).scalar() or 0

        actual_minutes = (await self.db.execute(
            select(func.sum(Task.actual_minutes)).where(
                Task.employee_id == employee_id,
                Task.status == "completed",
                Task.completed_at >= datetime.combine(today, datetime.min.time()),
            )
        )).scalar() or 0

        # Departments involved
        dept_result = await self.db.execute(
            select(Task.department).where(
                Task.employee_id == employee_id,
                Task.status.in_(["pending", "in_progress"]),
            ).distinct()
        )
        departments = [r[0] for r in dept_result.all()]

        # Workload level
        if pending + in_progress <= 3:
            level = "light"
        elif pending + in_progress <= 8:
            level = "moderate"
        elif pending + in_progress <= 15:
            level = "heavy"
        else:
            level = "overloaded"

        return WorkloadSummaryResponse(
            employee_id=employee_id,
            date=today,
            total_tasks=total,
            completed_tasks=completed,
            overdue_tasks=overdue,
            pending_tasks=pending,
            in_progress_tasks=in_progress,
            total_estimated_minutes=est_minutes,
            total_actual_minutes=actual_minutes,
            departments_involved=departments,
            workload_level=level,
        )

    def _compute_base_priority_score(self, priority: str, due_date: date | None) -> int:
        """Compute a numeric priority score (0-100)."""
        base = {"urgent": 90, "high": 70, "medium": 50, "low": 30}.get(priority, 50)

        if due_date:
            days_until = (due_date - date.today()).days
            if days_until < 0:
                base = min(base + 20, 100)  # Overdue boost
            elif days_until <= 1:
                base = min(base + 10, 100)  # Due soon boost
            elif days_until <= 3:
                base = min(base + 5, 100)

        return base

    def _rule_based_prioritization(self, tasks: list[Task], today: date) -> dict:
        """Fallback rule-based prioritization when AI is unavailable."""
        scored = []
        for t in tasks:
            score = self._compute_base_priority_score(t.priority, t.due_date)
            if t.due_date and t.due_date < today:
                score += 20
            if t.category in ("scheme_processing", "citizen_service", "grievance_followup"):
                score += 10
            scored.append((t, min(score, 100)))

        scored.sort(key=lambda x: x[1], reverse=True)

        task_order = []
        for rank, (task, score) in enumerate(scored, 1):
            task_order.append({
                "task_id": str(task.id),
                "rank": rank,
                "reason_te": self._get_rule_reason_te(task, today),
            })

        return {
            "task_order": task_order,
            "summary_te": f"ఈ రోజు {len(scored)} tasks ఉన్నాయి. ముందుగా urgent tasks పూర్తి చేయండి.",
            "summary_en": f"You have {len(scored)} tasks today. Complete urgent tasks first.",
        }

    def _get_rule_reason_te(self, task: Task, today: date) -> str:
        """Generate Telugu reason for task priority (rule-based)."""
        if task.due_date and task.due_date < today:
            return "⚠️ గడువు దాటింది — వెంటనే పూర్తి చేయండి"
        if task.priority == "urgent":
            return "🔴 అత్యవసరం"
        if task.priority == "high":
            return "🟠 అధిక ప్రాధాన్యత"
        if task.category in ("scheme_processing", "citizen_service"):
            return "👤 పౌరుల సేవ — ప్రాధాన్యత"
        if task.due_date and (task.due_date - today).days <= 1:
            return "⏰ రేపు గడువు"
        return "📋 సాధారణ task"

    def _to_response(self, task: Task) -> TaskResponse:
        """Convert Task model to response schema."""
        return TaskResponse(
            id=task.id,
            employee_id=task.employee_id,
            title_te=task.title_te,
            title_en=task.title_en,
            department=task.department,
            category=task.category,
            priority=task.priority,
            priority_score=task.priority_score,
            due_date=task.due_date,
            estimated_minutes=task.estimated_minutes,
            status=task.status,
            started_at=task.started_at,
            completed_at=task.completed_at,
            actual_minutes=task.actual_minutes,
            source=task.source,
            ai_priority_reason_te=task.ai_priority_reason_te,
            is_ai_suggested=task.is_ai_suggested,
            is_recurring=task.is_recurring,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
