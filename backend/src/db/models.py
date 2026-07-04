from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class TripRecordModel(Base):
    __tablename__ = "trips"

    trip_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    clarification_needed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clarification_questions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    destination_research_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    itinerary_plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stay_recommendation_plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local_transport_plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    food_recommendation_plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget_assessment_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    solo_women_safety_assessment_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_assessment_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_required")
    approval_actor_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    approval_actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    approval_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approval_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    route_trace_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    workflow_state_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    node_outputs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    governance_flags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    short_term_memory_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    run_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class PlannerJobModel(Base):
    __tablename__ = "planner_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    queue_job_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    trip_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dead_lettered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class WorkflowRunModel(Base):
    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_step: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_completed_step: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    state_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    queue_job_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    dead_lettered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rerun_of_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class WorkflowRunStepModel(Base):
    __tablename__ = "workflow_run_steps"

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trip_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    node_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider_endpoint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_references_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
