from __future__ import annotations

from typing import Optional
from uuid import uuid4

from src.agents.travel_planner.schemas import TripRequest
from src.application.jobs.mappers import planner_job_response_from_record
from src.application.jobs.schemas import PlannerJobResponse
from src.core.request_context import get_request_context
from src.domain.jobs.repositories import JobRepository
from src.services.audit_service import AuditService
from src.services.workflow_runtime_service import WorkflowRuntimeService


class CreateTripAsyncUseCase:
    def __init__(
        self,
        *,
        workflow_runtime_service: WorkflowRuntimeService,
        audit_service: AuditService,
    ) -> None:
        self.workflow_runtime_service = workflow_runtime_service
        self.audit_service = audit_service

    def execute(self, request: TripRequest) -> PlannerJobResponse:
        request_context = get_request_context()
        idempotency_key = str(uuid4())
        job = self.workflow_runtime_service.enqueue_async(request, idempotency_key=idempotency_key)
        self.audit_service.record_event(
            event_type="request_received",
            request_id=request_context.request_id if request_context else None,
            run_id=job.run_id,
            job_id=job.job_id,
            actor_id=request_context.actor_id if request_context else None,
            actor_role=request_context.actor_role if request_context else None,
            status="accepted",
            payload={"destination": request.destination, "mode": "async"},
        )
        return planner_job_response_from_record(job)


class GetJobUseCase:
    def __init__(self, *, job_repository: JobRepository) -> None:
        self.job_repository = job_repository

    def execute(self, job_id: str) -> Optional[PlannerJobResponse]:
        job = self.job_repository.get(job_id)
        if job is None:
            return None
        return planner_job_response_from_record(job)
