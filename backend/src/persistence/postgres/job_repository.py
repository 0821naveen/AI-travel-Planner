from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import PlannerJobModel
from src.domain.jobs.models import JobStatus, PlannerJob
from src.domain.jobs.repositories import JobRepository


class PostgresJobRepository(JobRepository):
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, job: PlannerJob) -> PlannerJob:
        with self.session_factory() as session:
            record = session.get(PlannerJobModel, job.job_id)
            if record is None:
                record = PlannerJobModel(job_id=job.job_id)

            record.job_type = job.job_type
            record.status = job.status.value
            record.created_at = job.created_at
            record.updated_at = job.updated_at
            record.run_id = job.run_id
            record.queue_job_id = job.queue_job_id
            record.trip_id = job.trip_id
            record.error = job.error
            record.retry_count = job.retry_count
            record.max_retries = job.max_retries
            record.timeout_seconds = job.timeout_seconds
            record.cancellation_requested = job.cancellation_requested
            record.cancelled_at = job.cancelled_at
            record.dead_lettered_at = job.dead_lettered_at
            record.idempotency_key = job.idempotency_key
            record.metadata_json = json.dumps(job.metadata)

            session.add(record)
            session.commit()

        return job

    def get(self, job_id: str) -> Optional[PlannerJob]:
        with self.session_factory() as session:
            record = session.get(PlannerJobModel, job_id)
            if record is None:
                return None
            return PlannerJob(
                job_id=record.job_id,
                job_type=record.job_type,
                status=JobStatus(record.status),
                created_at=record.created_at,
                updated_at=record.updated_at,
                run_id=record.run_id,
                queue_job_id=record.queue_job_id,
                trip_id=record.trip_id,
                error=record.error,
                retry_count=record.retry_count,
                max_retries=record.max_retries,
                timeout_seconds=record.timeout_seconds,
                cancellation_requested=record.cancellation_requested,
                cancelled_at=record.cancelled_at,
                dead_lettered_at=record.dead_lettered_at,
                idempotency_key=record.idempotency_key,
                metadata=json.loads(record.metadata_json or "{}"),
            )

    def get_by_run_id(self, run_id: str) -> Optional[PlannerJob]:
        with self.session_factory() as session:
            statement = select(PlannerJobModel).where(PlannerJobModel.run_id == run_id)
            record = session.execute(statement).scalar_one_or_none()
            if record is None:
                return None
            return PlannerJob(
                job_id=record.job_id,
                job_type=record.job_type,
                status=JobStatus(record.status),
                created_at=record.created_at,
                updated_at=record.updated_at,
                run_id=record.run_id,
                queue_job_id=record.queue_job_id,
                trip_id=record.trip_id,
                error=record.error,
                retry_count=record.retry_count,
                max_retries=record.max_retries,
                timeout_seconds=record.timeout_seconds,
                cancellation_requested=record.cancellation_requested,
                cancelled_at=record.cancelled_at,
                dead_lettered_at=record.dead_lettered_at,
                idempotency_key=record.idempotency_key,
                metadata=json.loads(record.metadata_json or "{}"),
            )
