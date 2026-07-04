"""add trip state persistence and audit events

Revision ID: 20260509_000002
Revises: 20260509_000001
Create Date: 2026-05-09 00:00:02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_000002"
down_revision = "20260509_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("run_id", sa.String(length=64), nullable=True))
    op.add_column("trips", sa.Column("state_version", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("trips", sa.Column("workflow_state_json", sa.Text(), nullable=True))
    op.add_column("trips", sa.Column("node_outputs_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column(
        "trips",
        sa.Column("governance_flags_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("trips", sa.Column("short_term_memory_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("trips", sa.Column("run_summary_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")))

    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("trip_id", sa.String(length=64), nullable=True),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("node_name", sa.String(length=128), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=True),
        sa.Column("provider_name", sa.String(length=64), nullable=True),
        sa.Column("provider_endpoint", sa.String(length=128), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=128), nullable=True),
        sa.Column("source_references_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_audit_events_run_id", "audit_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_run_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_column("trips", "run_summary_json")
    op.drop_column("trips", "short_term_memory_json")
    op.drop_column("trips", "governance_flags_json")
    op.drop_column("trips", "node_outputs_json")
    op.drop_column("trips", "workflow_state_json")
    op.drop_column("trips", "state_version")
    op.drop_column("trips", "run_id")
