from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.domain.workflows.models import WorkflowExecutionMode, WorkflowRunStatus


class WorkflowRunResponse(BaseModel):
    run_id: str
    trip_id: str
    execution_mode: WorkflowExecutionMode
    status: WorkflowRunStatus
    created_at: datetime
    updated_at: datetime
    current_step: Optional[str] = None
    last_completed_step: Optional[str] = None
    job_id: Optional[str] = None
    queue_job_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 0
    timeout_seconds: int = 300
    cancellation_requested: bool = False
    rerun_of_run_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
