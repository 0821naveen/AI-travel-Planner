from __future__ import annotations

from typing import Protocol

from src.domain.workflows.step_models import WorkflowRunStep


class WorkflowRunStepRepository(Protocol):
    def save(self, step: WorkflowRunStep) -> WorkflowRunStep: ...

    def list_by_run_id(self, run_id: str) -> list[WorkflowRunStep]: ...
