from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, TypedDict

from src.agents.travel_planner.schemas import (
    BudgetAssessment,
    ClarificationQuestion,
    DestinationResearchReport,
    FoodRecommendationPlan,
    ItineraryPlan,
    LocalTransportPlan,
    ReviewAssessment,
    SoloWomenSafetyAssessment,
    StayRecommendationPlan,
    TripRequest,
    TripStatus,
)


@dataclass
class PlannerContext:
    trip_id: str
    request: TripRequest
    run_id: Optional[str] = None
    state_version: int = 2
    status: TripStatus = TripStatus.DRAFT
    clarification_questions: list[ClarificationQuestion] = field(default_factory=list)
    research_signals: dict[str, Any] = field(default_factory=dict)
    destination_research: Optional[DestinationResearchReport] = None
    itinerary_plan: Optional[ItineraryPlan] = None
    stay_recommendation_plan: Optional[StayRecommendationPlan] = None
    local_transport_plan: Optional[LocalTransportPlan] = None
    food_recommendation_plan: Optional[FoodRecommendationPlan] = None
    budget_assessment: Optional[BudgetAssessment] = None
    solo_women_safety_assessment: Optional[SoloWomenSafetyAssessment] = None
    review_assessment: Optional[ReviewAssessment] = None
    itinerary_notes: list[str] = field(default_factory=list)
    budget_warnings: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)
    route_trace: list[str] = field(default_factory=list)
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    governance_flags: list[str] = field(default_factory=list)
    short_term_memory: dict[str, Any] = field(
        default_factory=lambda: {
            "tool_budget": {
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "total_latency_ms": 0.0,
                "tool_calls": 0,
            },
            "recent_events": [],
        }
    )
    tool_audit_log: list[dict[str, Any]] = field(default_factory=list)
    run_summary: dict[str, Any] = field(default_factory=dict)
    audit_events: list[dict[str, Any]] = field(default_factory=list)

    def mark(self, agent_name: str) -> None:
        self.route_trace.append(agent_name)

    def record_node_output(self, agent_name: str, payload: dict[str, Any]) -> None:
        self.node_outputs[agent_name] = payload
        self.run_summary["last_agent"] = agent_name

    def append_memory_event(self, event: dict[str, Any]) -> None:
        recent_events = self.short_term_memory.setdefault("recent_events", [])
        if isinstance(recent_events, list):
            recent_events.append(event)
            del recent_events[:-25]

    def append_tool_audit(self, event: dict[str, Any]) -> None:
        self.tool_audit_log.append(event)
        del self.tool_audit_log[:-100]
        self.append_memory_event({"type": "tool_call", **event})

    def append_audit_event(self, event: dict[str, Any]) -> None:
        self.audit_events.append(event)
        del self.audit_events[:-250]
        self.append_memory_event({"type": "audit_event", **event})


class PlannerState(TypedDict):
    trip_id: str
    request: TripRequest
    run_id: Optional[str]
    state_version: int
    status: TripStatus
    clarification_questions: List[ClarificationQuestion]
    research_signals: Dict[str, Any]
    destination_research: Optional[DestinationResearchReport]
    itinerary_plan: Optional[ItineraryPlan]
    stay_recommendation_plan: Optional[StayRecommendationPlan]
    local_transport_plan: Optional[LocalTransportPlan]
    food_recommendation_plan: Optional[FoodRecommendationPlan]
    budget_assessment: Optional[BudgetAssessment]
    solo_women_safety_assessment: Optional[SoloWomenSafetyAssessment]
    review_assessment: Optional[ReviewAssessment]
    itinerary_notes: List[str]
    budget_warnings: List[str]
    review_notes: List[str]
    route_trace: List[str]
    node_outputs: Dict[str, Dict[str, Any]]
    governance_flags: List[str]
    short_term_memory: Dict[str, Any]
    tool_audit_log: List[Dict[str, Any]]
    run_summary: Dict[str, Any]
    audit_events: List[Dict[str, Any]]


def planner_state_from_context(context: PlannerContext) -> PlannerState:
    return PlannerState(**asdict(context))


def planner_context_from_state(state: PlannerState) -> PlannerContext:
    return PlannerContext(**state)


def serialize_planner_context(context: PlannerContext) -> str:
    payload = {
        "trip_id": context.trip_id,
        "request": context.request.model_dump(mode="json"),
        "run_id": context.run_id,
        "state_version": context.state_version,
        "status": context.status.value,
        "clarification_questions": [item.model_dump(mode="json") for item in context.clarification_questions],
        "research_signals": context.research_signals,
        "destination_research": context.destination_research.model_dump(mode="json")
        if context.destination_research
        else None,
        "itinerary_plan": context.itinerary_plan.model_dump(mode="json") if context.itinerary_plan else None,
        "stay_recommendation_plan": context.stay_recommendation_plan.model_dump(mode="json")
        if context.stay_recommendation_plan
        else None,
        "local_transport_plan": context.local_transport_plan.model_dump(mode="json")
        if context.local_transport_plan
        else None,
        "food_recommendation_plan": context.food_recommendation_plan.model_dump(mode="json")
        if context.food_recommendation_plan
        else None,
        "budget_assessment": context.budget_assessment.model_dump(mode="json") if context.budget_assessment else None,
        "solo_women_safety_assessment": context.solo_women_safety_assessment.model_dump(mode="json")
        if context.solo_women_safety_assessment
        else None,
        "review_assessment": context.review_assessment.model_dump(mode="json") if context.review_assessment else None,
        "itinerary_notes": list(context.itinerary_notes),
        "budget_warnings": list(context.budget_warnings),
        "review_notes": list(context.review_notes),
        "route_trace": list(context.route_trace),
        "node_outputs": context.node_outputs,
        "governance_flags": list(context.governance_flags),
        "short_term_memory": context.short_term_memory,
        "tool_audit_log": list(context.tool_audit_log),
        "run_summary": context.run_summary,
        "audit_events": list(context.audit_events),
    }
    return json.dumps(payload)


def deserialize_planner_context(payload: str) -> PlannerContext:
    raw = json.loads(payload)
    return PlannerContext(
        trip_id=raw["trip_id"],
        request=TripRequest.model_validate(raw["request"]),
        run_id=raw.get("run_id"),
        state_version=int(raw.get("state_version", 1)),
        status=TripStatus(raw["status"]),
        clarification_questions=[ClarificationQuestion.model_validate(item) for item in raw["clarification_questions"]],
        research_signals=dict(raw.get("research_signals") or {}),
        destination_research=DestinationResearchReport.model_validate(raw["destination_research"])
        if raw.get("destination_research")
        else None,
        itinerary_plan=ItineraryPlan.model_validate(raw["itinerary_plan"]) if raw.get("itinerary_plan") else None,
        stay_recommendation_plan=StayRecommendationPlan.model_validate(raw["stay_recommendation_plan"])
        if raw.get("stay_recommendation_plan")
        else None,
        local_transport_plan=LocalTransportPlan.model_validate(raw["local_transport_plan"])
        if raw.get("local_transport_plan")
        else None,
        food_recommendation_plan=FoodRecommendationPlan.model_validate(raw["food_recommendation_plan"])
        if raw.get("food_recommendation_plan")
        else None,
        budget_assessment=BudgetAssessment.model_validate(raw["budget_assessment"])
        if raw.get("budget_assessment")
        else None,
        solo_women_safety_assessment=SoloWomenSafetyAssessment.model_validate(raw["solo_women_safety_assessment"])
        if raw.get("solo_women_safety_assessment")
        else None,
        review_assessment=ReviewAssessment.model_validate(raw["review_assessment"])
        if raw.get("review_assessment")
        else None,
        itinerary_notes=list(raw.get("itinerary_notes") or []),
        budget_warnings=list(raw.get("budget_warnings") or []),
        review_notes=list(raw.get("review_notes") or []),
        route_trace=list(raw.get("route_trace") or []),
        node_outputs=dict(raw.get("node_outputs") or {}),
        governance_flags=list(raw.get("governance_flags") or []),
        short_term_memory=dict(raw.get("short_term_memory") or {}),
        tool_audit_log=list(raw.get("tool_audit_log") or []),
        run_summary=dict(raw.get("run_summary") or {}),
        audit_events=list(raw.get("audit_events") or []),
    )
