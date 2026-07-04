"""add workflow run steps

Revision ID: 20260509_000003
Revises: 20260509_000002
Create Date: 2026-05-09 00:00:03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_000003"
down_revision = "20260509_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_run_steps",
        sa.Column("step_id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_workflow_run_steps_run_id", "workflow_run_steps", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_run_steps_run_id", table_name="workflow_run_steps")
    op.drop_table("workflow_run_steps")
