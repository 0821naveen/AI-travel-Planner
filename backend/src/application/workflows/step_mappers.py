from __future__ import annotations

from src.application.workflows.step_schemas import WorkflowRunStepResponse
from src.domain.workflows.step_models import WorkflowRunStep


def workflow_run_step_response_from_record(record: WorkflowRunStep) -> WorkflowRunStepResponse:
    return WorkflowRunStepResponse(
        step_id=record.step_id,
        run_id=record.run_id,
        step_name=record.step_name,
        sequence=record.sequence,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        error=record.error,
        retry_count=record.retry_count,
        metadata=record.metadata,
    )
