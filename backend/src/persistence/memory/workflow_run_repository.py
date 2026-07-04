from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

from src.domain.workflows.models import WorkflowExecutionMode, WorkflowRun
from src.domain.workflows.repositories import WorkflowRunRepository


class InMemoryWorkflowRunRepository(WorkflowRunRepository):
    def __init__(self) -> None:
        self._records: Dict[str, WorkflowRun] = {}
        self._lock = Lock()

    def save(self, run: WorkflowRun) -> WorkflowRun:
        with self._lock:
            self._records[run.run_id] = run
        return run

    def get(self, run_id: str) -> Optional[WorkflowRun]:
        with self._lock:
            return self._records.get(run_id)

    def list_recent(self, limit: int = 20) -> list[WorkflowRun]:
        with self._lock:
            records = sorted(self._records.values(), key=lambda item: item.updated_at, reverse=True)
            return records[:limit]

    def get_by_job_id(self, job_id: str) -> Optional[WorkflowRun]:
        with self._lock:
            for record in self._records.values():
                if record.job_id == job_id:
                    return record
        return None

    def find_by_idempotency_key(
        self,
        *,
        idempotency_key: str,
        execution_mode: WorkflowExecutionMode,
    ) -> Optional[WorkflowRun]:
        with self._lock:
            for record in self._records.values():
                if record.idempotency_key == idempotency_key and record.execution_mode == execution_mode:
                    return record
        return None
