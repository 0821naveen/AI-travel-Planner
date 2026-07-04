from __future__ import annotations

from collections import defaultdict

from src.agents.travel_planner.schemas import BudgetTier, TravelerConstraints, TripPurpose, TripRequest, TripStatus
from src.agents.travel_planner.state import PlannerContext
from src.core.config import AppSettings, DatabaseSettings, SecuritySettings, Settings, WorkflowRuntimeSettings
from src.core.logging import get_logger
from src.domain.jobs.models import JobStatus
from src.domain.workflows.models import WorkflowRunStatus
from src.messaging.redis_queue import InMemoryWorkflowQueue
from src.persistence.memory.job_repository import InMemoryJobRepository
from src.persistence.memory.trip_repository import InMemoryTripRepository
from src.persistence.memory.workflow_run_repository import InMemoryWorkflowRunRepository
from src.persistence.memory.workflow_run_step_repository import InMemoryWorkflowRunStepRepository
from src.services.workflow_runtime_service import WorkflowRuntimeService


def build_request() -> TripRequest:
    return TripRequest(
        origin_city="Bengaluru",
        destination="Mysuru",
        start_date="2026-05-10",
        end_date="2026-05-12",
        traveler_count=2,
        trip_purpose=TripPurpose.LEISURE,
        total_budget=12000,
        budget_tier=BudgetTier.MID_RANGE,
        pace="balanced",
        interests=["food", "culture"],
        accommodation_preference="hotel",
        transport_preference="train",
        constraints=TravelerConstraints(notes="No special constraints."),
    )


def build_settings(*, max_retries: int) -> Settings:
    return Settings(
        app=AppSettings(environment="test"),
        database=DatabaseSettings(url="sqlite+pysqlite:///:memory:"),
        security=SecuritySettings(enabled=False),
        workflow_runtime=WorkflowRuntimeSettings(max_retries=max_retries, job_timeout_seconds=5),
    )


class FlakyGraph:
    def __init__(self) -> None:
        self._attempts: dict[str, int] = defaultdict(int)

    def initial_step(self) -> str:
        return "clarification_validator"

    def execute_step(self, step_name: str, context: PlannerContext) -> PlannerContext:
        self._attempts[context.run_id or context.trip_id] += 1
        if self._attempts[context.run_id or context.trip_id] == 1:
            raise RuntimeError("transient provider failure")
        context.route_trace.append(step_name)
        context.status = TripStatus.RESEARCH_READY
        return context

    def next_step(self, step_name: str, context: PlannerContext):
        return None


class AlwaysFailGraph:
    def initial_step(self) -> str:
        return "clarification_validator"

    def execute_step(self, step_name: str, context: PlannerContext) -> PlannerContext:
        raise RuntimeError("persistent provider failure")

    def next_step(self, step_name: str, context: PlannerContext):
        return None


def build_service(*, graph, max_retries: int) -> tuple[WorkflowRuntimeService, InMemoryJobRepository, InMemoryWorkflowRunRepository]:
    job_repository = InMemoryJobRepository()
    run_repository = InMemoryWorkflowRunRepository()
    service = WorkflowRuntimeService(
        settings=build_settings(max_retries=max_retries),
        graph=graph,
        trip_repository=InMemoryTripRepository(),
        job_repository=job_repository,
        workflow_run_repository=run_repository,
        workflow_run_step_repository=InMemoryWorkflowRunStepRepository(),
        workflow_queue=InMemoryWorkflowQueue(settings=build_settings(max_retries=max_retries)),
        logger=get_logger("test.workflow_resilience"),
    )
    return service, job_repository, run_repository


def test_async_run_retries_and_then_succeeds():
    service, job_repository, run_repository = build_service(graph=FlakyGraph(), max_retries=2)

    job = service.enqueue_async(build_request())
    assert job.run_id is not None

    service.run_async_job(run_id=job.run_id, job_id=job.job_id)
    queued_job = job_repository.get(job.job_id)
    queued_run = run_repository.get(job.run_id)
    assert queued_job is not None
    assert queued_run is not None
    assert queued_job.status == JobStatus.QUEUED
    assert queued_run.status == WorkflowRunStatus.QUEUED
    assert queued_job.retry_count == 1

    service.run_async_job(run_id=job.run_id, job_id=job.job_id)
    completed_job = job_repository.get(job.job_id)
    completed_run = run_repository.get(job.run_id)
    assert completed_job is not None
    assert completed_run is not None
    assert completed_job.status == JobStatus.SUCCEEDED
    assert completed_run.status == WorkflowRunStatus.SUCCEEDED


def test_async_run_dead_letters_after_retry_budget_exhausted():
    service, job_repository, run_repository = build_service(graph=AlwaysFailGraph(), max_retries=1)

    job = service.enqueue_async(build_request())
    assert job.run_id is not None

    service.run_async_job(run_id=job.run_id, job_id=job.job_id)
    service.run_async_job(run_id=job.run_id, job_id=job.job_id)

    failed_job = job_repository.get(job.job_id)
    failed_run = run_repository.get(job.run_id)
    assert failed_job is not None
    assert failed_run is not None
    assert failed_job.status == JobStatus.DEAD_LETTERED
    assert failed_run.status == WorkflowRunStatus.DEAD_LETTERED
    assert failed_job.retry_count == 2
