from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.agents.travel_planner.schemas import CreateTripResponse, EvidenceItem, HumanApprovalRecord, TripStatus


class AdminTripListItemResponse(BaseModel):
    trip_id: str
    run_id: Optional[str] = None
    destination: str
    start_date: str
    end_date: str
    traveler_count: int
    status: TripStatus
    approval: HumanApprovalRecord
    updated_at: datetime
    review_confidence: float = 0.0
    review_summary: Optional[str] = None
    governance_flags: list[str] = Field(default_factory=list)


class AdminDashboardResponse(BaseModel):
    generated_at: datetime
    active_plans: int = 0
    awaiting_clarification: int = 0
    ready_for_review: int = 0
    completed: int = 0
    recent_trips: list[AdminTripListItemResponse] = Field(default_factory=list)
    review_queue: list[AdminTripListItemResponse] = Field(default_factory=list)


class ApprovalDecisionRequest(BaseModel):
    action: str
    note: Optional[str] = None


class TripReviewDetailResponse(BaseModel):
    trip: CreateTripResponse
    approval: HumanApprovalRecord
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    governance_flags: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)

