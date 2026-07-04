from __future__ import annotations

from datetime import datetime

from src.agents.travel_planner.schemas import (
    BudgetTier,
    EvidenceItem,
    HumanApprovalRecord,
    HumanApprovalStatus,
    ReviewAssessment,
    TravelerConstraints,
    TripPurpose,
    TripRequest,
    TripStatus,
)
from src.application.admin.schemas import ApprovalDecisionRequest
from src.core.security import ActorContext, ActorRole
from src.domain.audit.models import AuditEvent
from src.domain.trips.models import TripRecord
from src.persistence.memory.trip_repository import InMemoryTripRepository
from src.services.audit_service import AuditService
from src.services.operator_review_service import OperatorReviewService


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event

    def list_by_run_id(self, run_id: str) -> list[AuditEvent]:
        return [event for event in self.events if event.run_id == run_id]


def build_trip_record(
    *,
    trip_id: str,
    status: TripStatus,
    human_approval: HumanApprovalRecord,
    review_assessment: ReviewAssessment,
    evidence_items: list[EvidenceItem] | None = None,
    governance_flags: list[str] | None = None,
) -> TripRecord:
    return TripRecord(
        trip_id=trip_id,
        request=TripRequest(
            origin_city="Bengaluru",
            destination="Mysuru",
            start_date="2026-05-10",
            end_date="2026-05-12",
            traveler_count=2,
            trip_purpose=TripPurpose.LEISURE,
            total_budget=12000,
            budget_tier=BudgetTier.MID_RANGE,
            pace="balanced",
            interests=["food", "culture"],
            accommodation_preference="hotel",
            transport_preference="train",
            constraints=TravelerConstraints(notes="No special constraints."),
        ),
        status=status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        run_id=f"run-{trip_id}",
        review_assessment=review_assessment,
        human_approval=human_approval,
        evidence_items=list(evidence_items or []),
        governance_flags=list(governance_flags or []),
    )


def test_operator_review_dashboard_and_decision_flow():
    repository = InMemoryTripRepository()
    audit_repository = InMemoryAuditRepository()
    service = OperatorReviewService(repository=repository, audit_service=AuditService(repository=audit_repository))

    trip = build_trip_record(
        trip_id="trip-1",
        status=TripStatus.READY_FOR_REVIEW,
        human_approval=HumanApprovalRecord(status=HumanApprovalStatus.PENDING),
        review_assessment=ReviewAssessment(
            destination="Mysuru",
            approved=False,
            summary="Manual approval required because evidence is mixed.",
            consistency_score=0.62,
            issues=["Budget and itinerary confidence diverge."],
            recommended_fixes=["Review price assumptions."],
            final_notes=[],
            confidence=0.58,
        ),
        evidence_items=[
            EvidenceItem(
                category="research_source",
                title="Source A",
                detail="Independent source summary.",
                url="https://example.com/source-a",
            )
        ],
        governance_flags=["budget_confidence_low"],
    )
    repository.save(trip)

    dashboard = service.dashboard()
    assert dashboard.ready_for_review == 1
    assert len(dashboard.review_queue) == 1

    detail = service.get_review_detail(trip_id="trip-1")
    assert detail is not None
    assert detail.approval.status == HumanApprovalStatus.PENDING
    assert detail.evidence_items[0].title == "Source A"

    approved = service.apply_approval_decision(
        trip_id="trip-1",
        decision=ApprovalDecisionRequest(action="approve", note="Evidence reviewed and accepted."),
        actor=ActorContext(actor_id="operator@example.com", role=ActorRole.OPERATOR),
        request_id="req-1",
    )
    assert approved is not None
    assert approved.approval.status == HumanApprovalStatus.APPROVED
    assert approved.trip.trip.status == TripStatus.COMPLETED
    assert audit_repository.events[-1].event_type == "approval_granted"


def test_operator_review_reject_keeps_trip_in_review():
    repository = InMemoryTripRepository()
    audit_repository = InMemoryAuditRepository()
    service = OperatorReviewService(repository=repository, audit_service=AuditService(repository=audit_repository))

    trip = build_trip_record(
        trip_id="trip-2",
        status=TripStatus.READY_FOR_REVIEW,
        human_approval=HumanApprovalRecord(status=HumanApprovalStatus.PENDING),
        review_assessment=ReviewAssessment(
            destination="Mysuru",
            approved=False,
            summary="Manual approval required.",
            consistency_score=0.5,
            issues=["Missing safety confidence."],
            recommended_fixes=["Re-run safety review."],
            final_notes=[],
            confidence=0.45,
        ),
    )
    repository.save(trip)

    rejected = service.apply_approval_decision(
        trip_id="trip-2",
        decision=ApprovalDecisionRequest(action="reject", note="Need stronger evidence."),
        actor=ActorContext(actor_id="admin@example.com", role=ActorRole.ADMIN),
    )
    assert rejected is not None
    assert rejected.approval.status == HumanApprovalStatus.REJECTED
    assert rejected.trip.trip.status == TripStatus.READY_FOR_REVIEW
    assert "Need stronger evidence." in (rejected.trip.review_assessment.issues if rejected.trip.review_assessment else [])
    assert audit_repository.events[-1].event_type == "approval_rejected"
