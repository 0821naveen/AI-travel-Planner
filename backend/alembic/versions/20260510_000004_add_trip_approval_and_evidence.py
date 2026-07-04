"""add trip approval and evidence fields

Revision ID: 20260510_000004
Revises: 20260509_000003
Create Date: 2026-05-10 00:00:04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260510_000004"
down_revision = "20260509_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="not_required"))
    op.add_column("trips", sa.Column("approval_actor_id", sa.String(length=128), nullable=True))
    op.add_column("trips", sa.Column("approval_actor_role", sa.String(length=32), nullable=True))
    op.add_column("trips", sa.Column("approval_reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("trips", sa.Column("approval_note", sa.Text(), nullable=True))
    op.add_column("trips", sa.Column("evidence_items_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("trips", "evidence_items_json")
    op.drop_column("trips", "approval_note")
    op.drop_column("trips", "approval_reviewed_at")
    op.drop_column("trips", "approval_actor_role")
    op.drop_column("trips", "approval_actor_id")
    op.drop_column("trips", "approval_status")

