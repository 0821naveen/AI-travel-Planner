from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.core.config import Settings
from src.domain.jobs.models import PlannerJob
from src.domain.workflows.models import WorkflowRun

WORKFLOW_WORKER_ENTRYPOINT = "src.workers.workflow_worker.execute_planner_run"


@dataclass
class EnqueuedWorkflowJob:
    queue_job_id: str


class InMemoryWorkflowQueue:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    def enqueue(self, *, run: WorkflowRun, job: PlannerJob) -> EnqueuedWorkflowJob:
        return EnqueuedWorkflowJob(queue_job_id=f"in-memory:{run.run_id}:attempt:{job.retry_count}")

    def request_cancel(self, *, queue_job_id: Optional[str]) -> None:
        return


class RedisWorkflowQueue:
    def __init__(self, *, redis_client, settings: Settings) -> None:
        from rq import Queue

        self.redis_client = redis_client
        self.settings = settings
        self.queue = Queue(settings.workflow_runtime.queue_name, connection=redis_client)

    def enqueue(self, *, run: WorkflowRun, job: PlannerJob) -> EnqueuedWorkflowJob:
        queue_job_id = f"planner-run:{run.run_id}:attempt:{job.retry_count}"
        self.queue.enqueue(
            WORKFLOW_WORKER_ENTRYPOINT,
            run.run_id,
            job.job_id,
            job_id=queue_job_id,
            job_timeout=job.timeout_seconds,
            result_ttl=0,
            failure_ttl=86400,
        )
        return EnqueuedWorkflowJob(queue_job_id=queue_job_id)

    def request_cancel(self, *, queue_job_id: Optional[str]) -> None:
        if not queue_job_id:
            return

        try:
            from rq.command import send_stop_job_command

            send_stop_job_command(self.redis_client, queue_job_id)
        except Exception:
            return


def build_workflow_queue(settings: Settings):
    try:
        from redis import Redis
        from rq import Queue  # noqa: F401
    except Exception as exc:
        if settings.app.environment in {"dev", "staging", "prod"}:
            raise RuntimeError("Redis/RQ dependencies are required for the workflow runtime.") from exc
        return InMemoryWorkflowQueue(settings=settings)

    redis_client = Redis.from_url(settings.redis.url, decode_responses=True)
    return RedisWorkflowQueue(redis_client=redis_client, settings=settings)
