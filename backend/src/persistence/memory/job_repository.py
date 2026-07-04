from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

from src.domain.jobs.models import PlannerJob
from src.domain.jobs.repositories import JobRepository


class InMemoryJobRepository(JobRepository):
    def __init__(self) -> None:
        self._records: Dict[str, PlannerJob] = {}
        self._lock = Lock()

    def save(self, job: PlannerJob) -> PlannerJob:
        with self._lock:
            self._records[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[PlannerJob]:
        with self._lock:
            return self._records.get(job_id)

    def get_by_run_id(self, run_id: str) -> Optional[PlannerJob]:
        with self._lock:
            for record in self._records.values():
                if record.run_id == run_id:
                    return record
        return None
