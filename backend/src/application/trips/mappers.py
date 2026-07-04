from __future__ import annotations

from datetime import datetime

from src.agents.travel_planner.schemas import (
    CreateTripResponse,
    EvidenceItem,
    HumanApprovalRecord,
    HumanApprovalStatus,
    TripSummaryResponse,
)
from src.agents.travel_planner.state import PlannerContext, serialize_planner_context
from src.domain.trips.models import TripRecord


def trip_record_from_context(trip_id: str, context: PlannerContext) -> TripRecord:
    now = datetime.utcnow()
    return TripRecord(
        trip_id=trip_id,
        request=context.request,
        status=context.status,
        created_at=now,
        updated_at=now,
        run_id=context.run_id,
        state_version=context.state_version,
        clarification_needed=bool(context.clarification_questions),
        clarification_questions=list(context.clarification_questions),
        destination_research=context.destination_research,
        itinerary_plan=context.itinerary_plan,
        stay_recommendation_plan=context.stay_recommendation_plan,
        local_transport_plan=context.local_transport_plan,
        food_recommendation_plan=context.food_recommendation_plan,
        budget_assessment=context.budget_assessment,
        solo_women_safety_assessment=context.solo_women_safety_assessment,
        review_assessment=context.review_assessment,
        human_approval=_default_human_approval(context),
        evidence_items=_build_evidence_items(context),
        route_trace=list(context.route_trace),
        workflow_state_json=serialize_planner_context(context),
        node_outputs=dict(context.node_outputs),
        governance_flags=list(context.governance_flags),
        short_term_memory=dict(context.short_term_memory),
        run_summary=dict(context.run_summary),
    )


def create_trip_response_from_record(record: TripRecord, *, run_id: str | None = None) -> CreateTripResponse:
    request = record.request
    return CreateTripResponse(
        run_id=run_id or record.run_id,
        trip=TripSummaryResponse(
            trip_id=record.trip_id,
            status=record.status,
            destination=request.destination,
            start_date=request.start_date,
            end_date=request.end_date,
            traveler_count=request.traveler_count,
        ),
        clarification_needed=record.clarification_needed,
        clarification_questions=record.clarification_questions,
        destination_research=record.destination_research,
        itinerary_plan=record.itinerary_plan,
        stay_recommendation_plan=record.stay_recommendation_plan,
        local_transport_plan=record.local_transport_plan,
        food_recommendation_plan=record.food_recommendation_plan,
        budget_assessment=record.budget_assessment,
        solo_women_safety_assessment=record.solo_women_safety_assessment,
        review_assessment=record.review_assessment,
        human_approval=record.human_approval,
        evidence_items=record.evidence_items,
        route_trace=record.route_trace,
    )


def _default_human_approval(context: PlannerContext) -> HumanApprovalRecord:
    requires_review = bool(
        context.review_assessment is not None
        and (not context.review_assessment.approved or context.status.value == "ready_for_review")
    )
    return HumanApprovalRecord(
        status=HumanApprovalStatus.PENDING if requires_review else HumanApprovalStatus.NOT_REQUIRED
    )


def _build_evidence_items(context: PlannerContext) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    if context.destination_research is not None:
        for source in context.destination_research.sources[:8]:
            evidence.append(
                EvidenceItem(
                    category="research_source",
                    title=source.title,
                    detail=source.snippet,
                    url=source.url,
                )
            )
        for area in context.destination_research.recommended_areas[:4]:
            evidence.append(
                EvidenceItem(
                    category="recommended_area",
                    title=area,
                    detail="Area recommended by destination research.",
                )
            )

    if context.review_assessment is not None:
        for issue in context.review_assessment.issues[:5]:
            evidence.append(
                EvidenceItem(
                    category="review_issue",
                    title="Review issue",
                    detail=issue,
                )
            )

    for flag in context.governance_flags[:5]:
        evidence.append(
            EvidenceItem(
                category="governance_flag",
                title="Governance flag",
                detail=flag,
            )
        )

    return evidence
