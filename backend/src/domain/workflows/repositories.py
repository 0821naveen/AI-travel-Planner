from __future__ import annotations

from typing import Optional, Protocol

from src.domain.workflows.models import WorkflowExecutionMode, WorkflowRun


class WorkflowRunRepository(Protocol):
    def save(self, run: WorkflowRun) -> WorkflowRun: ...

    def get(self, run_id: str) -> Optional[WorkflowRun]: ...

    def list_recent(self, limit: int = 20) -> list[WorkflowRun]: ...

    def get_by_job_id(self, job_id: str) -> Optional[WorkflowRun]: ...

    def find_by_idempotency_key(
        self,
        *,
        idempotency_key: str,
        execution_mode: WorkflowExecutionMode,
    ) -> Optional[WorkflowRun]: ...
