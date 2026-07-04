from __future__ import annotations

from src.application.workflows.schemas import WorkflowRunResponse
from src.domain.workflows.models import WorkflowRun


def workflow_run_response_from_record(record: WorkflowRun) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        run_id=record.run_id,
        trip_id=record.trip_id,
        execution_mode=record.execution_mode,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        current_step=record.current_step,
        last_completed_step=record.last_completed_step,
        job_id=record.job_id,
        queue_job_id=record.queue_job_id,
        idempotency_key=record.idempotency_key,
        error=record.error,
        retry_count=record.retry_count,
        max_retries=record.max_retries,
        timeout_seconds=record.timeout_seconds,
        cancellation_requested=record.cancellation_requested,
        rerun_of_run_id=record.rerun_of_run_id,
        metadata=record.metadata,
    )
