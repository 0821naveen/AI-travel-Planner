from __future__ import annotations

from logging import Logger
from typing import Optional
from uuid import uuid4

from src.agents.travel_planner.graph import TravelPlannerGraph
from src.agents.travel_planner.schemas import CreateTripResponse, TripRequest
from src.application.trips.mappers import create_trip_response_from_record, trip_record_from_context
from src.core.request_context import get_request_context
from src.core.response_shaping import shape_trip_response
from src.domain.trips.guardrails import apply_trip_guardrails
from src.domain.trips.repositories import TripRepository
from src.services.audit_service import AuditService


class CreateTripUseCase:
    def __init__(
        self,
        *,
        graph: TravelPlannerGraph,
        repository: TripRepository,
        logger: Logger,
        audit_service: AuditService | None = None,
    ) -> None:
        self.graph = graph
        self.repository = repository
        self.logger = logger
        self.audit_service = audit_service

    def execute(self, request: TripRequest, *, run_id: str | None = None) -> CreateTripResponse:
        trip_id = str(uuid4())
        effective_run_id = run_id or str(uuid4())
        request_context = get_request_context()
        self.logger.info(
            "trip.create.started",
            extra={
                "trip_id": trip_id,
                "run_id": effective_run_id,
                "destination": request.destination,
                "traveler_count": request.traveler_count,
            },
        )
        if self.audit_service is not None:
            self.audit_service.record_event(
                event_type="workflow_started",
                request_id=request_context.request_id if request_context else None,
                trip_id=trip_id,
                run_id=effective_run_id,
                actor_id=request_context.actor_id if request_context else None,
                actor_role=request_context.actor_role if request_context else None,
                status="started",
                payload={"destination": request.destination},
            )
        try:
            context = self.graph.bootstrap_trip(trip_id=trip_id, request=request, run_id=effective_run_id)
            context = apply_trip_guardrails(context)
        except Exception as exc:
            if self.audit_service is not None:
                self.audit_service.record_event(
                    event_type="run_failed",
                    request_id=request_context.request_id if request_context else None,
                    trip_id=trip_id,
                    run_id=effective_run_id,
                    actor_id=request_context.actor_id if request_context else None,
                    actor_role=request_context.actor_role if request_context else None,
                    status="failed",
                    payload={"error": str(exc)},
                )
            raise

        record = trip_record_from_context(trip_id, context)
        self.repository.save(record)
        if self.audit_service is not None:
            for event in context.audit_events:
                self.audit_service.record_event(
                    event_type=str(event.get("event_type")),
                    request_id=request_context.request_id if request_context else None,
                    trip_id=trip_id,
                    run_id=effective_run_id,
                    actor_id=request_context.actor_id if request_context else None,
                    actor_role=request_context.actor_role if request_context else None,
                    status=str(event.get("status")) if event.get("status") is not None else None,
                    node_name=str(event.get("node_name")) if event.get("node_name") is not None else None,
                    tool_name=str(event.get("tool_name")) if event.get("tool_name") is not None else None,
                    provider_name=str(event.get("provider_name")) if event.get("provider_name") is not None else None,
                    provider_endpoint=str(event.get("provider_endpoint")) if event.get("provider_endpoint") is not None else None,
                    payload={key: value for key, value in event.items() if key not in {"event_type"}},
                )
            if context.review_assessment and not context.review_assessment.approved:
                self.audit_service.record_event(
                    event_type="approval_requested",
                    request_id=request_context.request_id if request_context else None,
                    trip_id=trip_id,
                    run_id=effective_run_id,
                    actor_id=request_context.actor_id if request_context else None,
                    actor_role=request_context.actor_role if request_context else None,
                    status="manual_review_required",
                    payload={"issues": context.review_assessment.issues},
                )
            else:
                self.audit_service.record_event(
                    event_type="approval_granted",
                    request_id=request_context.request_id if request_context else None,
                    trip_id=trip_id,
                    run_id=effective_run_id,
                    actor_id=request_context.actor_id if request_context else None,
                    actor_role=request_context.actor_role if request_context else None,
                    status="approved",
                )
        self.logger.info(
            "trip.create.completed",
            extra={
                "trip_id": trip_id,
                "run_id": effective_run_id,
                "status": record.status.value,
                "route_trace": record.route_trace,
            },
        )
        return shape_trip_response(create_trip_response_from_record(record, run_id=effective_run_id))


class GetTripUseCase:
    def __init__(self, *, repository: TripRepository) -> None:
        self.repository = repository

    def execute(self, trip_id: str) -> Optional[CreateTripResponse]:
        record = self.repository.get(trip_id)
        if record is None:
            return None
        return create_trip_response_from_record(record)
