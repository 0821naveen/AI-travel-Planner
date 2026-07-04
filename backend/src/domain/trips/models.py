from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional

from src.agents.travel_planner.schemas import (
    BudgetAssessment,
    ClarificationQuestion,
    DestinationResearchReport,
    EvidenceItem,
    FoodRecommendationPlan,
    HumanApprovalRecord,
    ItineraryPlan,
    LocalTransportPlan,
    ReviewAssessment,
    SoloWomenSafetyAssessment,
    StayRecommendationPlan,
    TripRequest,
    TripStatus,
)


@dataclass
class TripRecord:
    trip_id: str
    request: TripRequest
    status: TripStatus
    created_at: datetime
    updated_at: datetime
    run_id: Optional[str] = None
    state_version: int = 2
    clarification_needed: bool = False
    clarification_questions: List[ClarificationQuestion] = field(default_factory=list)
    destination_research: Optional[DestinationResearchReport] = None
    itinerary_plan: Optional[ItineraryPlan] = None
    stay_recommendation_plan: Optional[StayRecommendationPlan] = None
    local_transport_plan: Optional[LocalTransportPlan] = None
    food_recommendation_plan: Optional[FoodRecommendationPlan] = None
    budget_assessment: Optional[BudgetAssessment] = None
    solo_women_safety_assessment: Optional[SoloWomenSafetyAssessment] = None
    review_assessment: Optional[ReviewAssessment] = None
    human_approval: HumanApprovalRecord = field(default_factory=HumanApprovalRecord)
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    route_trace: List[str] = field(default_factory=list)
    workflow_state_json: Optional[str] = None
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    governance_flags: List[str] = field(default_factory=list)
    short_term_memory: dict[str, Any] = field(default_factory=dict)
    run_summary: dict[str, Any] = field(default_factory=dict)
