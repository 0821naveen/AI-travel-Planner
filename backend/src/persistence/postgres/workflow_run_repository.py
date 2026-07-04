from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.agents.travel_planner.schemas import TripRequest
from src.agents.travel_planner.state import deserialize_planner_context, serialize_planner_context
from src.db.models import WorkflowRunModel
from src.domain.workflows.models import WorkflowExecutionMode, WorkflowRun, WorkflowRunStatus
from src.domain.workflows.repositories import WorkflowRunRepository


class PostgresWorkflowRunRepository(WorkflowRunRepository):
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, run: WorkflowRun) -> WorkflowRun:
        with self.session_factory() as session:
            record = session.get(WorkflowRunModel, run.run_id)
            if record is None:
                record = WorkflowRunModel(run_id=run.run_id)

            record.trip_id = run.trip_id
            record.execution_mode = run.execution_mode.value
            record.status = run.status.value
            record.created_at = run.created_at
            record.updated_at = run.updated_at
            record.current_step = run.current_step
            record.last_completed_step = run.last_completed_step
            record.state_json = serialize_planner_context(run.context) if run.context else None
            record.request_json = run.request.model_dump_json()
            record.job_id = run.job_id
            record.queue_job_id = run.queue_job_id
            record.idempotency_key = run.idempotency_key
            record.error = run.error
            record.retry_count = run.retry_count
            record.max_retries = run.max_retries
            record.timeout_seconds = run.timeout_seconds
            record.cancellation_requested = run.cancellation_requested
            record.cancelled_at = run.cancelled_at
            record.dead_lettered_at = run.dead_lettered_at
            record.rerun_of_run_id = run.rerun_of_run_id
            record.metadata_json = json.dumps(run.metadata)

            session.add(record)
            session.commit()

        return run

    def get(self, run_id: str) -> Optional[WorkflowRun]:
        with self.session_factory() as session:
            record = session.get(WorkflowRunModel, run_id)
            return self._to_domain(record)

    def list_recent(self, limit: int = 20) -> list[WorkflowRun]:
        with self.session_factory() as session:
            statement = select(WorkflowRunModel).order_by(WorkflowRunModel.updated_at.desc()).limit(limit)
            return [self._to_domain(record) for record in session.execute(statement).scalars() if record is not None]

    def get_by_job_id(self, job_id: str) -> Optional[WorkflowRun]:
        with self.session_factory() as session:
            statement = select(WorkflowRunModel).where(WorkflowRunModel.job_id == job_id)
            record = session.execute(statement).scalar_one_or_none()
            return self._to_domain(record)

    def find_by_idempotency_key(
        self,
        *,
        idempotency_key: str,
        execution_mode: WorkflowExecutionMode,
    ) -> Optional[WorkflowRun]:
        with self.session_factory() as session:
            statement = select(WorkflowRunModel).where(
                WorkflowRunModel.idempotency_key == idempotency_key,
                WorkflowRunModel.execution_mode == execution_mode.value,
            )
            record = session.execute(statement).scalar_one_or_none()
            return self._to_domain(record)

    @staticmethod
    def _to_domain(record: WorkflowRunModel | None) -> Optional[WorkflowRun]:
        if record is None:
            return None

        return WorkflowRun(
            run_id=record.run_id,
            trip_id=record.trip_id,
            request=TripRequest.model_validate_json(record.request_json),
            execution_mode=WorkflowExecutionMode(record.execution_mode),
            status=WorkflowRunStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            current_step=record.current_step,
            last_completed_step=record.last_completed_step,
            context=deserialize_planner_context(record.state_json) if record.state_json else None,
            job_id=record.job_id,
            queue_job_id=record.queue_job_id,
            idempotency_key=record.idempotency_key,
            error=record.error,
            retry_count=record.retry_count,
            max_retries=record.max_retries,
            timeout_seconds=record.timeout_seconds,
            cancellation_requested=record.cancellation_requested,
            cancelled_at=record.cancelled_at,
            dead_lettered_at=record.dead_lettered_at,
            rerun_of_run_id=record.rerun_of_run_id,
            metadata=json.loads(record.metadata_json or "{}"),
        )
