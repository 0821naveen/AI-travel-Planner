from __future__ import annotations

from datetime import datetime

from src.agents.travel_planner.schemas import HumanApprovalRecord, HumanApprovalStatus, TripStatus
from src.application.admin.schemas import (
    AdminDashboardResponse,
    AdminTripListItemResponse,
    ApprovalDecisionRequest,
    TripReviewDetailResponse,
)
from src.application.trips.mappers import create_trip_response_from_record
from src.core.security import ActorContext
from src.domain.trips.models import TripRecord
from src.domain.trips.repositories import TripRepository
from src.services.audit_service import AuditService


class OperatorReviewService:
    def __init__(self, *, repository: TripRepository, audit_service: AuditService) -> None:
        self.repository = repository
        self.audit_service = audit_service

    def dashboard(self, *, limit: int = 10) -> AdminDashboardResponse:
        recent = self.repository.list_recent(limit=limit)
        review_queue = self.repository.list_review_queue(limit=limit)
        return AdminDashboardResponse(
            generated_at=datetime.utcnow(),
            active_plans=sum(1 for trip in recent if trip.status in {TripStatus.RESEARCH_READY, TripStatus.ITINERARY_READY}),
            awaiting_clarification=sum(1 for trip in recent if trip.status == TripStatus.AWAITING_CLARIFICATION),
            ready_for_review=sum(1 for trip in recent if trip.human_approval.status == HumanApprovalStatus.PENDING),
            completed=sum(1 for trip in recent if trip.status == TripStatus.COMPLETED),
            recent_trips=[self._to_list_item(trip) for trip in recent],
            review_queue=[self._to_list_item(trip) for trip in review_queue],
        )

    def review_queue(self, *, limit: int = 20) -> list[AdminTripListItemResponse]:
        return [self._to_list_item(trip) for trip in self.repository.list_review_queue(limit=limit)]

    def get_review_detail(self, *, trip_id: str) -> TripReviewDetailResponse | None:
        trip = self.repository.get(trip_id)
        if trip is None:
            return None
        return TripReviewDetailResponse(
            trip=create_trip_response_from_record(trip),
            approval=trip.human_approval,
            evidence_items=trip.evidence_items,
            governance_flags=trip.governance_flags,
            review_notes=list(trip.review_assessment.issues if trip.review_assessment else []),
        )

    def apply_approval_decision(
        self,
        *,
        trip_id: str,
        decision: ApprovalDecisionRequest,
        actor: ActorContext,
        request_id: str | None = None,
    ) -> TripReviewDetailResponse | None:
        trip = self.repository.get(trip_id)
        if trip is None:
            return None

        normalized = decision.action.strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValueError("Approval action must be 'approve' or 'reject'.")

        trip.updated_at = datetime.utcnow()
        trip.human_approval = HumanApprovalRecord(
            status=HumanApprovalStatus.APPROVED if normalized == "approve" else HumanApprovalStatus.REJECTED,
            reviewer_actor_id=actor.actor_id,
            reviewer_role=actor.role.value,
            reviewed_at=trip.updated_at,
            note=decision.note,
        )
        trip.status = TripStatus.COMPLETED if normalized == "approve" else TripStatus.READY_FOR_REVIEW
        if trip.review_assessment is not None:
            trip.review_assessment.approved = normalized == "approve"
            if decision.note and normalized == "reject":
                trip.review_assessment.issues = list(dict.fromkeys([*trip.review_assessment.issues, decision.note]))
            if decision.note and normalized == "approve":
                trip.review_assessment.final_notes = list(dict.fromkeys([*trip.review_assessment.final_notes, decision.note]))

        self.repository.save(trip)
        self.audit_service.record_event(
            event_type="approval_granted" if normalized == "approve" else "approval_rejected",
            request_id=request_id,
            trip_id=trip.trip_id,
            run_id=trip.run_id,
            actor_id=actor.actor_id,
            actor_role=actor.role.value,
            status=trip.status.value,
            payload={"note": decision.note, "approval_status": trip.human_approval.status.value},
        )
        return self.get_review_detail(trip_id=trip.trip_id)

    @staticmethod
    def _to_list_item(trip: TripRecord) -> AdminTripListItemResponse:
        return AdminTripListItemResponse(
            trip_id=trip.trip_id,
            run_id=trip.run_id,
            destination=trip.request.destination,
            start_date=trip.request.start_date,
            end_date=trip.request.end_date,
            traveler_count=trip.request.traveler_count,
            status=trip.status,
            approval=trip.human_approval,
            updated_at=trip.updated_at,
            review_confidence=trip.review_assessment.confidence if trip.review_assessment else 0.0,
            review_summary=trip.review_assessment.summary if trip.review_assessment else None,
            governance_flags=list(trip.governance_flags),
        )

