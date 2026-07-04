from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.domain.workflows.step_models import WorkflowRunStepStatus


class WorkflowRunStepResponse(BaseModel):
    step_id: str
    run_id: str
    step_name: str
    sequence: int
    status: WorkflowRunStepStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
