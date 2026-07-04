from __future__ import annotations

from typing import Optional, Protocol

from src.domain.jobs.models import PlannerJob


class JobRepository(Protocol):
    def save(self, job: PlannerJob) -> PlannerJob: ...

    def get(self, job_id: str) -> Optional[PlannerJob]: ...

    def get_by_run_id(self, run_id: str) -> Optional[PlannerJob]: ...
