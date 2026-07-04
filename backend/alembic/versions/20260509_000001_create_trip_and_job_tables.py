"""create trip and job tables

Revision ID: 20260509_000001
Revises:
Create Date: 2026-05-09 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planner_jobs",
        sa.Column("job_id", sa.String(length=64), primary_key=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("trip_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_table(
        "trips",
        sa.Column("trip_id", sa.String(length=64), primary_key=True),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("clarification_needed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("clarification_questions_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("destination_research_json", sa.Text(), nullable=True),
        sa.Column("itinerary_plan_json", sa.Text(), nullable=True),
        sa.Column("stay_recommendation_plan_json", sa.Text(), nullable=True),
        sa.Column("local_transport_plan_json", sa.Text(), nullable=True),
        sa.Column("food_recommendation_plan_json", sa.Text(), nullable=True),
        sa.Column("budget_assessment_json", sa.Text(), nullable=True),
        sa.Column("solo_women_safety_assessment_json", sa.Text(), nullable=True),
        sa.Column("review_assessment_json", sa.Text(), nullable=True),
        sa.Column("route_trace_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_table("trips")
    op.drop_table("planner_jobs")
