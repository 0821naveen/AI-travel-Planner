from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.domain.jobs.models import JobStatus


class PlannerJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: JobStatus
    run_id: Optional[str] = None
    queue_job_id: Optional[str] = None
    trip_id: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 0
    timeout_seconds: int = 300
    cancellation_requested: bool = False
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
