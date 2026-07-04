from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import WorkflowRunStepModel
from src.domain.workflows.step_models import WorkflowRunStep, WorkflowRunStepStatus
from src.domain.workflows.step_repositories import WorkflowRunStepRepository


class PostgresWorkflowRunStepRepository(WorkflowRunStepRepository):
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, step: WorkflowRunStep) -> WorkflowRunStep:
        with self.session_factory() as session:
            record = session.get(WorkflowRunStepModel, step.step_id)
            if record is None:
                record = WorkflowRunStepModel(step_id=step.step_id)

            record.run_id = step.run_id
            record.step_name = step.step_name
            record.sequence = step.sequence
            record.status = step.status.value
            record.started_at = step.started_at
            record.completed_at = step.completed_at
            record.error = step.error
            record.retry_count = step.retry_count
            record.metadata_json = json.dumps(step.metadata)

            session.add(record)
            session.commit()

        return step

    def list_by_run_id(self, run_id: str) -> list[WorkflowRunStep]:
        with self.session_factory() as session:
            statement = (
                select(WorkflowRunStepModel)
                .where(WorkflowRunStepModel.run_id == run_id)
                .order_by(WorkflowRunStepModel.sequence.asc())
            )
            return [self._to_domain(record) for record in session.execute(statement).scalars()]

    @staticmethod
    def _to_domain(record: WorkflowRunStepModel) -> WorkflowRunStep:
        return WorkflowRunStep(
            step_id=record.step_id,
            run_id=record.run_id,
            step_name=record.step_name,
            sequence=record.sequence,
            status=WorkflowRunStepStatus(record.status),
            started_at=record.started_at,
            completed_at=record.completed_at,
            error=record.error,
            retry_count=record.retry_count,
            metadata=json.loads(record.metadata_json or "{}"),
        )
