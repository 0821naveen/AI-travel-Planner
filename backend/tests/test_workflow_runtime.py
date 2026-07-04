from __future__ import annotations

from sqlalchemy import text

from src.agents.travel_planner.schemas import BudgetTier, TravelerConstraints, TripPurpose, TripRequest, TripStatus
from src.agents.travel_planner.state import PlannerContext
from src.core.config import AppSettings, DatabaseSettings, SecuritySettings, Settings
from src.core.logging import get_logger
from src.db.bootstrap import metadata
from src.db.session import build_engine
from src.messaging.redis_queue import InMemoryWorkflowQueue
from src.persistence.memory.job_repository import InMemoryJobRepository
from src.persistence.memory.trip_repository import InMemoryTripRepository
from src.persistence.memory.workflow_run_repository import InMemoryWorkflowRunRepository
from src.persistence.memory.workflow_run_step_repository import InMemoryWorkflowRunStepRepository
from src.services.audit_service import AuditService
from src.services.readiness_service import ReadinessService
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
        constraints=TravelerConstraints(),
    )


class FakeRuntimeGraph:
    def initial_step(self) -> str:
        return "clarification_validator"

    def execute_step(self, step_name: str, context: PlannerContext) -> PlannerContext:
        context.route_trace.append(step_name)
        context.status = TripStatus.RESEARCH_READY
        return context

    def next_step(self, step_name: str, context: PlannerContext):
        return None


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self.events = []

    def append(self, event):
        self.events.append(event)
        return event

    def list_by_run_id(self, run_id: str):
        return [event for event in self.events if event.run_id == run_id]


class FakeCoordinatorRuntime:
    def bootstrap_trip_with_progress(self, trip_id: str, request: TripRequest, *, run_id: str | None = None, progress_callback=None):
        context = PlannerContext(trip_id=trip_id, request=request, run_id=run_id, status=TripStatus.READY_FOR_REVIEW)
        context.route_trace.extend(["destination_research", "itinerary", "review"])
        context.append_audit_event(
            {
                "event_type": "tool_called",
                "run_id": run_id,
                "trip_id": trip_id,
                "node_name": "destination_research",
                "tool_name": "web_search",
                "provider_name": "tavily",
                "provider_endpoint": "/search",
                "status": "success",
                "latency_ms": 85.0,
            }
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "event_type": "coordinator_decision",
                    "step_name": "coordinator_agent",
                    "status": "running",
                    "next_roles": ["destination_research"],
                    "task_ids": ["research_destination"],
                    "rationale": "Research is the next required task.",
                }
            )
            progress_callback(
                {
                    "event_type": "specialist_started",
                    "step_name": "destination_research",
                    "status": "running",
                    "task_id": "research_destination",
                    "summary": "Destination Research started working on its assigned task.",
                }
            )
            progress_callback(
                {
                    "event_type": "specialist_completed",
                    "step_name": "destination_research",
                    "status": "succeeded",
                    "task_id": "research_destination",
                    "summary": "Destination research gathered source-backed planning context.",
                    "confidence": 0.81,
                }
            )
        return {"context": context, "ledger": None, "terminal_reason": "All tasks completed."}


def build_test_settings(*, database_url: str = "sqlite+pysqlite:///:memory:") -> Settings:
    return Settings(
        app=AppSettings(environment="test"),
        database=DatabaseSettings(url=database_url),
        security=SecuritySettings(enabled=False),
    )


def test_workflow_runtime_service_persists_step_records():
    settings = build_test_settings()
    step_repository = InMemoryWorkflowRunStepRepository()
    service = WorkflowRuntimeService(
        settings=settings,
        graph=FakeRuntimeGraph(),
        trip_repository=InMemoryTripRepository(),
        job_repository=InMemoryJobRepository(),
        workflow_run_repository=InMemoryWorkflowRunRepository(),
        workflow_run_step_repository=step_repository,
        workflow_queue=InMemoryWorkflowQueue(settings=settings),
        logger=get_logger("test.workflow_runtime"),
    )

    response = service.execute_sync(build_request())

    steps = step_repository.list_by_run_id(response.run_id)
    assert len(steps) == 1
    assert steps[0].step_name == "clarification_validator"
    assert steps[0].status.value == "succeeded"
    recent_runs = service.list_recent_runs(limit=5)
    assert len(recent_runs) == 1
    assert recent_runs[0].run_id == response.run_id


def test_workflow_runtime_service_persists_coordinator_audit_events():
    settings = build_test_settings()
    step_repository = InMemoryWorkflowRunStepRepository()
    audit_repository = InMemoryAuditRepository()
    service = WorkflowRuntimeService(
        settings=settings,
        graph=FakeRuntimeGraph(),
        coordinator_runtime=FakeCoordinatorRuntime(),
        trip_repository=InMemoryTripRepository(),
        job_repository=InMemoryJobRepository(),
        workflow_run_repository=InMemoryWorkflowRunRepository(),
        workflow_run_step_repository=step_repository,
        audit_service=AuditService(repository=audit_repository),
        workflow_queue=InMemoryWorkflowQueue(settings=settings),
        logger=get_logger("test.workflow_runtime"),
    )

    response = service.execute_sync(build_request())

    events = audit_repository.list_by_run_id(response.run_id)
    event_types = [event.event_type for event in events]
    assert "coordinator_decision" in event_types
    assert "specialist_started" in event_types
    assert "specialist_completed" in event_types
    assert "workflow_terminal_decision" in event_types
    assert "tool_called" in event_types


def test_readiness_service_reports_healthy_for_migrated_test_database(tmp_path):
    database_path = tmp_path / "readiness.db"
    settings = build_test_settings(database_url=f"sqlite+pysqlite:///{database_path}")
    engine = build_engine(settings)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260611_000006')"))

    service = ReadinessService(
        settings=settings,
        engine=engine,
        workflow_queue=InMemoryWorkflowQueue(settings=settings),
    )

    report = service.readiness_report()
    assert report["healthy"] is True, report
