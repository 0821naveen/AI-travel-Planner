from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from src.agents.travel_planner.schemas import TripRequest
from src.agents.travel_planner.state import PlannerContext


class WorkflowExecutionMode(str, Enum):
    SYNC = "sync"
    ASYNC = "async"


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"


@dataclass
class WorkflowRun:
    run_id: str
    trip_id: str
    request: TripRequest
    execution_mode: WorkflowExecutionMode
    status: WorkflowRunStatus
    created_at: datetime
    updated_at: datetime
    current_step: Optional[str] = None
    last_completed_step: Optional[str] = None
    context: Optional[PlannerContext] = None
    job_id: Optional[str] = None
    queue_job_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 0
    timeout_seconds: int = 300
    cancellation_requested: bool = False
    cancelled_at: Optional[datetime] = None
    dead_lettered_at: Optional[datetime] = None
    rerun_of_run_id: Optional[str] = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def terminal(self) -> bool:
        return self.status in {
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.DEAD_LETTERED,
        }
