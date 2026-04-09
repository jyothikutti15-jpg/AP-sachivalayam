"""Initial schema — all models for AP Sachivalayam AI Copilot.

Revision ID: 001
Revises: -
Create Date: 2026-04-09

Creates tables:
- secretariats, employees, citizens, beneficiaries
- schemes, scheme_faqs, kb_documents, kb_chunks (with pgvector)
- chat_sessions, messages
- form_templates, form_submissions
- grievances, grievance_comments
- tasks, daily_plans
- daily_metrics, burnout_indicators
- employee_performance
- audit_logs
- offline_queue_items
- training_sessions
- outreach_records
- circulars
- citizen_reminders
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- Core entities ---

    op.create_table(
        "secretariats",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("gsws_code", sa.String(20), unique=True, nullable=False),
        sa.Column("name_te", sa.Text, nullable=False),
        sa.Column("name_en", sa.Text),
        sa.Column("mandal", sa.String(100)),
        sa.Column("district", sa.String(100)),
        sa.Column("type", sa.String(20), default="village"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("secretariat_id", sa.Integer, sa.ForeignKey("secretariats.id")),
        sa.Column("phone_number", sa.String(15), unique=True, nullable=False),
        sa.Column("name_te", sa.Text, nullable=False),
        sa.Column("name_en", sa.Text),
        sa.Column("designation", sa.String(100)),
        sa.Column("department", sa.String(100)),
        sa.Column("role", sa.String(30), default="employee"),
        sa.Column("language", sa.String(5), default="te"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("onboarded_at", sa.DateTime(timezone=True)),
        sa.Column("password_hash", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "citizens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("phone_number", sa.String(15), unique=True, nullable=False),
        sa.Column("name_te", sa.Text),
        sa.Column("name_en", sa.Text),
        sa.Column("district", sa.String(100)),
        sa.Column("aadhaar_hash", sa.String(64)),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "beneficiaries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("secretariat_id", sa.Integer, sa.ForeignKey("secretariats.id")),
        sa.Column("aadhaar_hash", sa.String(64)),
        sa.Column("name_te", sa.Text, nullable=False),
        sa.Column("name_en", sa.Text),
        sa.Column("age", sa.Integer),
        sa.Column("gender", sa.String(10)),
        sa.Column("caste", sa.String(20)),
        sa.Column("income_annual", sa.Integer),
        sa.Column("ration_card_type", sa.String(20)),
        sa.Column("land_acres", sa.Float),
        sa.Column("is_disabled", sa.Boolean, default=False),
        sa.Column("disability_percentage", sa.Integer),
        sa.Column("occupation", sa.String(50)),
        sa.Column("enrolled_schemes", postgresql.JSONB),
        sa.Column("opt_out", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # --- Schemes & Knowledge ---

    op.create_table(
        "schemes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scheme_code", sa.String(50), unique=True, nullable=False),
        sa.Column("name_te", sa.Text, nullable=False),
        sa.Column("name_en", sa.Text, nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("description_te", sa.Text),
        sa.Column("description_en", sa.Text),
        sa.Column("eligibility_criteria", postgresql.JSONB, nullable=False),
        sa.Column("required_documents", postgresql.JSONB),
        sa.Column("benefit_amount", sa.Text),
        sa.Column("application_process_te", sa.Text),
        sa.Column("go_reference", sa.Text),
        sa.Column("effective_from", sa.Date),
        sa.Column("effective_to", sa.Date),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "scheme_faqs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scheme_id", sa.Integer, sa.ForeignKey("schemes.id"), nullable=False),
        sa.Column("question_te", sa.Text),
        sa.Column("question_en", sa.Text),
        sa.Column("answer_te", sa.Text),
        sa.Column("answer_en", sa.Text),
        sa.Column("frequency", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_url", sa.Text),
        sa.Column("content_te", sa.Text),
        sa.Column("content_en", sa.Text),
        sa.Column("department", sa.String(100)),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("language", sa.String(5), default="te"),
        sa.Column("embedding", postgresql.ARRAY(sa.Float)),  # pgvector
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Conversations ---

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("phone_number", sa.String(15), nullable=False),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id")),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_extra", postgresql.JSONB),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("intent", sa.String(50)),
        sa.Column("confidence", sa.Float),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Forms ---

    op.create_table(
        "form_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name_te", sa.Text, nullable=False),
        sa.Column("name_en", sa.Text, nullable=False),
        sa.Column("department", sa.String(100)),
        sa.Column("scheme_code", sa.String(50)),
        sa.Column("gsws_form_code", sa.String(20)),
        sa.Column("fields", postgresql.JSONB, nullable=False),
        sa.Column("output_format", sa.String(10), default="pdf"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "form_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("form_templates.id")),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("citizen_name", sa.Text),
        sa.Column("citizen_aadhaar_hash", sa.String(64)),
        sa.Column("field_values", postgresql.JSONB),
        sa.Column("confidence_scores", postgresql.JSONB),
        sa.Column("status", sa.String(20), default="draft"),
        sa.Column("pdf_url", sa.Text),
        sa.Column("gsws_submission_id", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # --- Grievances ---

    op.create_table(
        "grievances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference_number", sa.String(20), unique=True, nullable=False),
        sa.Column("filed_by_employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("secretariat_id", sa.Integer, sa.ForeignKey("secretariats.id")),
        sa.Column("citizen_name", sa.Text, nullable=False),
        sa.Column("citizen_phone", sa.String(15)),
        sa.Column("citizen_aadhaar_hash", sa.String(64)),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("subcategory", sa.String(50)),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("subject_te", sa.Text, nullable=False),
        sa.Column("description_te", sa.Text, nullable=False),
        sa.Column("description_en", sa.Text),
        sa.Column("assigned_to_employee_id", sa.Integer, sa.ForeignKey("employees.id")),
        sa.Column("escalation_level", sa.SmallInteger, default=0),
        sa.Column("status", sa.String(20), default="open", nullable=False),
        sa.Column("priority", sa.String(10), default="medium"),
        sa.Column("sla_deadline", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("resolution_notes_te", sa.Text),
        sa.Column("resolution_notes_en", sa.Text),
        sa.Column("citizen_satisfaction", sa.SmallInteger),
        sa.Column("attachment_urls", postgresql.JSONB),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("is_sla_breached", sa.Boolean, default=False),
        sa.Column("last_escalated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "grievance_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("grievance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grievances.id"), nullable=False),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("comment_text", sa.Text, nullable=False),
        sa.Column("comment_type", sa.String(20), default="note"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Tasks ---

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("secretariat_id", sa.Integer, sa.ForeignKey("secretariats.id")),
        sa.Column("title_te", sa.Text, nullable=False),
        sa.Column("title_en", sa.Text),
        sa.Column("description_te", sa.Text),
        sa.Column("description_en", sa.Text),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), default="general"),
        sa.Column("priority", sa.String(10), default="medium"),
        sa.Column("priority_score", sa.SmallInteger, default=50),
        sa.Column("due_date", sa.Date),
        sa.Column("estimated_minutes", sa.Integer, default=30),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("actual_minutes", sa.Integer),
        sa.Column("source", sa.String(20), default="manual"),
        sa.Column("source_reference_id", sa.String(50)),
        sa.Column("ai_priority_reason_te", sa.Text),
        sa.Column("ai_priority_reason_en", sa.Text),
        sa.Column("is_ai_suggested", sa.Boolean, default=False),
        sa.Column("is_recurring", sa.Boolean, default=False),
        sa.Column("recurrence_rule", sa.String(50)),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "daily_plans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("plan_date", sa.Date, nullable=False),
        sa.Column("task_order", postgresql.JSONB, nullable=False),
        sa.Column("total_estimated_minutes", sa.Integer, default=0),
        sa.Column("ai_summary_te", sa.Text),
        sa.Column("ai_summary_en", sa.Text),
        sa.Column("sent_via_whatsapp", sa.Boolean, default=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "plan_date"),
    )

    # --- Analytics ---

    op.create_table(
        "daily_metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id")),
        sa.Column("secretariat_id", sa.Integer, sa.ForeignKey("secretariats.id")),
        sa.Column("queries_handled", sa.Integer, default=0),
        sa.Column("forms_filled", sa.Integer, default=0),
        sa.Column("grievances_filed", sa.Integer, default=0),
        sa.Column("time_saved_minutes", sa.Integer, default=0),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "burnout_indicators",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id")),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("hours_before", sa.Float),
        sa.Column("hours_after", sa.Float),
        sa.Column("satisfaction_score", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "employee_performance",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("grievances_filed", sa.Integer, default=0),
        sa.Column("grievances_resolved", sa.Integer, default=0),
        sa.Column("avg_resolution_hours", sa.Float),
        sa.Column("sla_compliance_pct", sa.Float),
        sa.Column("tasks_completed", sa.Integer, default=0),
        sa.Column("tasks_overdue", sa.Integer, default=0),
        sa.Column("forms_processed", sa.Integer, default=0),
        sa.Column("queries_handled", sa.Integer, default=0),
        sa.Column("time_saved_minutes", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Audit & Offline ---

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id")),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(50)),
        sa.Column("old_values", postgresql.JSONB),
        sa.Column("new_values", postgresql.JSONB),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("status", sa.String(20), default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "offline_queue_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("message_type", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(20), default="queued"),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("last_error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # --- Training ---

    op.create_table(
        "training_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("scenario_category", sa.String(50)),
        sa.Column("difficulty", sa.String(20)),
        sa.Column("score", sa.Float),
        sa.Column("completed", sa.Boolean, default=False),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Outreach ---

    op.create_table(
        "outreach_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("beneficiary_id", sa.Integer, sa.ForeignKey("beneficiaries.id"), nullable=False),
        sa.Column("scheme_code", sa.String(50), nullable=False),
        sa.Column("match_score", sa.Float),
        sa.Column("status", sa.String(20), default="identified"),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # --- Feature 9: Circulars ---

    op.create_table(
        "circulars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference_number", sa.String(100), unique=True, nullable=False),
        sa.Column("title_te", sa.Text, nullable=False),
        sa.Column("title_en", sa.Text),
        sa.Column("content_te", sa.Text),
        sa.Column("content_en", sa.Text),
        sa.Column("summary_te", sa.Text),
        sa.Column("summary_en", sa.Text),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), default="go"),
        sa.Column("scheme_code", sa.String(50)),
        sa.Column("issued_date", sa.Date, nullable=False),
        sa.Column("effective_date", sa.Date),
        sa.Column("expiry_date", sa.Date),
        sa.Column("source_url", sa.Text),
        sa.Column("pdf_url", sa.Text),
        sa.Column("impact_level", sa.String(20), default="normal"),
        sa.Column("key_changes", postgresql.JSONB),
        sa.Column("affected_districts", postgresql.JSONB),
        sa.Column("tags", postgresql.JSONB),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("view_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # --- Feature 10: Citizen Reminders ---

    op.create_table(
        "citizen_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("secretariat_id", sa.Integer, sa.ForeignKey("secretariats.id")),
        sa.Column("citizen_name", sa.Text, nullable=False),
        sa.Column("citizen_phone", sa.String(15), nullable=False),
        sa.Column("citizen_aadhaar_hash", sa.String(64)),
        sa.Column("reminder_type", sa.String(30), nullable=False),
        sa.Column("scheme_code", sa.String(50)),
        sa.Column("scheme_name_te", sa.Text),
        sa.Column("message_te", sa.Text, nullable=False),
        sa.Column("message_en", sa.Text),
        sa.Column("pending_items", postgresql.JSONB),
        sa.Column("reminder_date", sa.Date, nullable=False),
        sa.Column("reminder_time", sa.String(5), default="09:00"),
        sa.Column("is_recurring", sa.Boolean, default=False),
        sa.Column("recurrence_rule", sa.String(30)),
        sa.Column("recurrence_end_date", sa.Date),
        sa.Column("status", sa.String(20), default="scheduled", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("send_count", sa.Integer, default=0),
        sa.Column("max_sends", sa.Integer, default=3),
        sa.Column("priority", sa.String(10), default="medium"),
        sa.Column("form_submission_id", sa.String(50)),
        sa.Column("grievance_reference", sa.String(20)),
        sa.Column("metadata_extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # --- Indexes ---

    op.create_index("ix_employees_phone", "employees", ["phone_number"])
    op.create_index("ix_schemes_code", "schemes", ["scheme_code"])
    op.create_index("ix_schemes_department", "schemes", ["department"])
    op.create_index("ix_grievances_reference", "grievances", ["reference_number"])
    op.create_index("ix_grievances_status", "grievances", ["status"])
    op.create_index("ix_grievances_category", "grievances", ["category"])
    op.create_index("ix_tasks_employee_status", "tasks", ["employee_id", "status"])
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"])
    op.create_index("ix_circulars_department", "circulars", ["department"])
    op.create_index("ix_circulars_scheme", "circulars", ["scheme_code"])
    op.create_index("ix_circulars_issued", "circulars", ["issued_date"])
    op.create_index("ix_reminders_date", "citizen_reminders", ["reminder_date"])
    op.create_index("ix_reminders_status", "citizen_reminders", ["status"])
    op.create_index("ix_reminders_employee", "citizen_reminders", ["employee_id"])


def downgrade() -> None:
    tables = [
        "citizen_reminders", "circulars", "outreach_records", "training_sessions",
        "offline_queue_items", "audit_logs", "employee_performance",
        "burnout_indicators", "daily_metrics", "daily_plans", "tasks",
        "grievance_comments", "grievances", "form_submissions", "form_templates",
        "messages", "chat_sessions", "kb_chunks", "kb_documents",
        "scheme_faqs", "schemes", "beneficiaries", "citizens",
        "employees", "secretariats",
    ]
    for table in tables:
        op.drop_table(table)
