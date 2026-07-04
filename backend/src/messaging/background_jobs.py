from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from logging import Logger
from typing import Callable, Dict, Optional
from uuid import uuid4

from src.domain.jobs.models import JobStatus, PlannerJob
from src.domain.jobs.repositories import JobRepository


class BackgroundJobProcessor:
    def __init__(
        self,
        *,
        repository: JobRepository,
        logger: Logger,
        max_workers: int = 2,
    ) -> None:
        self.repository = repository
        self.logger = logger
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="planner-job")
        self.futures: Dict[str, Future] = {}

    def submit(self, *, job_type: str, task: Callable[[PlannerJob], Optional[str]], run_id: str | None = None) -> PlannerJob:
        now = datetime.utcnow()
        job = PlannerJob(
            job_id=str(uuid4()),
            job_type=job_type,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
            run_id=run_id,
        )
        self.repository.save(job)
        future = self.executor.submit(self._run_task, job.job_id, task)
        self.futures[job.job_id] = future
        return job

    def _run_task(self, job_id: str, task: Callable[[PlannerJob], Optional[str]]) -> None:
        job = self.repository.get(job_id)
        if job is None:
            return

        job.status = JobStatus.RUNNING
        job.updated_at = datetime.utcnow()
        self.repository.save(job)
        self.logger.info("job.started", extra={"job_id": job.job_id})

        try:
            trip_id = task(job)
            if trip_id:
                job.trip_id = trip_id
            job.status = JobStatus.SUCCEEDED
            job.updated_at = datetime.utcnow()
            self.repository.save(job)
            self.logger.info("job.succeeded", extra={"job_id": job.job_id, "trip_id": job.trip_id or "-"})
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.updated_at = datetime.utcnow()
            job.error = str(exc)
            self.repository.save(job)
            self.logger.exception("job.failed", extra={"job_id": job.job_id})

    def shutdown(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=False)
