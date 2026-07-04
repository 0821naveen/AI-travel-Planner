from __future__ import annotations

from threading import Lock

from src.domain.workflows.step_models import WorkflowRunStep
from src.domain.workflows.step_repositories import WorkflowRunStepRepository


class InMemoryWorkflowRunStepRepository(WorkflowRunStepRepository):
    def __init__(self) -> None:
        self._records: dict[str, WorkflowRunStep] = {}
        self._lock = Lock()

    def save(self, step: WorkflowRunStep) -> WorkflowRunStep:
        with self._lock:
            self._records[step.step_id] = step
        return step

    def list_by_run_id(self, run_id: str) -> list[WorkflowRunStep]:
        with self._lock:
            return sorted(
                [record for record in self._records.values() if record.run_id == run_id],
                key=lambda record: record.sequence,
            )
