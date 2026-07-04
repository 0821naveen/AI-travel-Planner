from __future__ import annotations

from src.application.jobs.schemas import PlannerJobResponse
from src.domain.jobs.models import PlannerJob


def planner_job_response_from_record(record: PlannerJob) -> PlannerJobResponse:
    return PlannerJobResponse(
        job_id=record.job_id,
        job_type=record.job_type,
        status=record.status,
        run_id=record.run_id,
        queue_job_id=record.queue_job_id,
        trip_id=record.trip_id,
        error=record.error,
        retry_count=record.retry_count,
        max_retries=record.max_retries,
        timeout_seconds=record.timeout_seconds,
        cancellation_requested=record.cancellation_requested,
        idempotency_key=record.idempotency_key,
        metadata=record.metadata,
    )
