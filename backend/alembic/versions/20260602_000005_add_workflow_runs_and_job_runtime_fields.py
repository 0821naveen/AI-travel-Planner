"""add workflow runs and job runtime fields

Revision ID: 20260602_000005
Revises: 20260510_000004
Create Date: 2026-06-02 00:00:05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260602_000005"
down_revision = "20260510_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("planner_jobs", sa.Column("run_id", sa.String(length=64), nullable=True))
    op.add_column("planner_jobs", sa.Column("queue_job_id", sa.String(length=128), nullable=True))
    op.add_column("planner_jobs", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("planner_jobs", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("planner_jobs", sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"))
    op.add_column(
        "planner_jobs",
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("planner_jobs", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("planner_jobs", sa.Column("dead_lettered_at", sa.DateTime(), nullable=True))
    op.add_column("planner_jobs", sa.Column("idempotency_key", sa.String(length=128), nullable=True))

    op.create_table(
        "workflow_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("trip_id", sa.String(length=64), nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("current_step", sa.String(length=128), nullable=True),
        sa.Column("last_completed_step", sa.String(length=128), nullable=True),
        sa.Column("state_json", sa.Text(), nullable=True),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("queue_job_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(), nullable=True),
        sa.Column("rerun_of_run_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_workflow_runs_job_id", "workflow_runs", ["job_id"])
    op.create_index("ix_workflow_runs_trip_id", "workflow_runs", ["trip_id"])
    op.create_index("ix_workflow_runs_idempotency_key", "workflow_runs", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_workflow_runs_idempotency_key", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_trip_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_job_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")

    op.drop_column("planner_jobs", "idempotency_key")
    op.drop_column("planner_jobs", "dead_lettered_at")
    op.drop_column("planner_jobs", "cancelled_at")
    op.drop_column("planner_jobs", "cancellation_requested")
    op.drop_column("planner_jobs", "timeout_seconds")
    op.drop_column("planner_jobs", "max_retries")
    op.drop_column("planner_jobs", "retry_count")
    op.drop_column("planner_jobs", "queue_job_id")
    op.drop_column("planner_jobs", "run_id")
