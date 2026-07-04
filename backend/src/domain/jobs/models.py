from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"


@dataclass
class PlannerJob:
    job_id: str
    job_type: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    run_id: Optional[str] = None
    queue_job_id: Optional[str] = None
    trip_id: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 0
    timeout_seconds: int = 300
    cancellation_requested: bool = False
    cancelled_at: Optional[datetime] = None
    dead_lettered_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
