from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from src.agents.travel_planner.schemas import BudgetTier, TravelerConstraints, TripPurpose, TripRequest
from src.core.config import (
    AppSettings,
    DatabaseSettings,
    ObservabilitySettings,
    SecuritySettings,
    Settings,
)
from src.core.logging import get_logger
from src.db.bootstrap import metadata
from src.db.session import build_engine, build_session_factory
from src.domain.workflows.models import WorkflowExecutionMode, WorkflowRun, WorkflowRunStatus
from src.domain.workflows.step_models import WorkflowRunStep, WorkflowRunStepStatus
from src.persistence.postgres.audit_repository import PostgresAuditEventRepository
from src.persistence.postgres.workflow_run_repository import PostgresWorkflowRunRepository
from src.persistence.postgres.workflow_run_step_repository import PostgresWorkflowRunStepRepository
from src.services.audit_service import AuditService
from src.services.observability_service import ObservabilityService


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


def build_settings(*, database_url: str) -> Settings:
    return Settings(
        app=AppSettings(environment="test"),
        database=DatabaseSettings(url=database_url),
        security=SecuritySettings(enabled=False),
        observability=ObservabilitySettings(
            metrics_lookback_hours=24,
            stuck_run_threshold_minutes=1,
            failure_rate_alert_threshold=0.1,
            provider_failure_alert_threshold=1,
            dead_letter_alert_threshold=1,
        ),
    )


def test_observability_metrics_and_trace(tmp_path):
    database_path = tmp_path / "observability.db"
    settings = build_settings(database_url=f"sqlite+pysqlite:///{database_path}")
    engine = build_engine(settings)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260611_000006')"))

    session_factory = build_session_factory(engine)
    run_repository = PostgresWorkflowRunRepository(session_factory=session_factory)
    step_repository = PostgresWorkflowRunStepRepository(session_factory=session_factory)
    audit_repository = PostgresAuditEventRepository(session_factory=session_factory)
    audit_service = AuditService(repository=audit_repository)
    service = ObservabilityService(
        settings=settings,
        session_factory=session_factory,
        workflow_run_repository=run_repository,
        workflow_run_step_repository=step_repository,
        audit_repository=audit_repository,
        logger=get_logger("test.observability"),
    )

    request = build_request()
    now = datetime.utcnow()
    succeeded_run = WorkflowRun(
        run_id=str(uuid4()),
        trip_id=str(uuid4()),
        request=request,
        execution_mode=WorkflowExecutionMode.SYNC,
        status=WorkflowRunStatus.SUCCEEDED,
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=9),
    )
    dead_lettered_run = WorkflowRun(
        run_id=str(uuid4()),
        trip_id=str(uuid4()),
        request=request,
        execution_mode=WorkflowExecutionMode.ASYNC,
        status=WorkflowRunStatus.DEAD_LETTERED,
        created_at=now - timedelta(minutes=8),
        updated_at=now - timedelta(minutes=6),
        retry_count=2,
        error="provider timeout",
    )
    stuck_run = WorkflowRun(
        run_id=str(uuid4()),
        trip_id=str(uuid4()),
        request=request,
        execution_mode=WorkflowExecutionMode.ASYNC,
        status=WorkflowRunStatus.RUNNING,
        created_at=now - timedelta(minutes=20),
        updated_at=now - timedelta(minutes=5),
        current_step="destination_research_agent",
    )
    run_repository.save(succeeded_run)
    run_repository.save(dead_lettered_run)
    run_repository.save(stuck_run)

    step_repository.save(
        WorkflowRunStep(
            step_id=str(uuid4()),
            run_id=succeeded_run.run_id,
            step_name="clarification_validator",
            sequence=1,
            status=WorkflowRunStepStatus.SUCCEEDED,
            started_at=now - timedelta(minutes=10),
            completed_at=now - timedelta(minutes=10) + timedelta(milliseconds=150),
            retry_count=0,
            metadata={},
        )
    )
    step_repository.save(
        WorkflowRunStep(
            step_id=str(uuid4()),
            run_id=dead_lettered_run.run_id,
            step_name="destination_research_agent",
            sequence=1,
            status=WorkflowRunStepStatus.FAILED,
            started_at=now - timedelta(minutes=8),
            completed_at=now - timedelta(minutes=8) + timedelta(milliseconds=300),
            retry_count=2,
            error="provider timeout",
            metadata={},
        )
    )

    audit_service.record_event(
        event_type="tool_called",
        run_id=succeeded_run.run_id,
        trip_id=succeeded_run.trip_id,
        node_name="destination_research",
        tool_name="web_search",
        provider_name="tavily",
        provider_endpoint="/search",
        status="success",
        payload={"total_tokens": 220, "estimated_cost_usd": 0.0012, "latency_ms": 120.5},
    )
    audit_service.record_event(
        event_type="tool_failed",
        run_id=dead_lettered_run.run_id,
        trip_id=dead_lettered_run.trip_id,
        node_name="destination_research",
        tool_name="web_search",
        provider_name="tavily",
        provider_endpoint="/search",
        status="execution_failed",
        payload={"latency_ms": 250.0},
    )
    audit_service.record_event(
        event_type="specialist_completed",
        run_id=succeeded_run.run_id,
        trip_id=succeeded_run.trip_id,
        node_name="destination_research",
        status="succeeded",
        payload={"summary": "Destination research gathered source-backed planning context.", "confidence": 0.82},
    )
    audit_service.record_event(
        event_type="coordinator_decision",
        run_id=succeeded_run.run_id,
        trip_id=succeeded_run.trip_id,
        node_name="coordinator_agent",
        status="running",
        payload={
            "next_roles": ["destination_research"],
            "task_ids": ["research_destination"],
            "rationale": "Research is the next required task.",
        },
    )

    metrics = service.metrics_report()
    assert metrics.runs.total_runs == 3
    assert metrics.runs.succeeded_runs == 1
    assert metrics.runs.dead_lettered_runs == 1
    assert metrics.runs.retry_count_total == 2
    assert metrics.token_usage_total == 220
    assert metrics.cost_usd_total == 0.0012
    assert metrics.provider_metrics[0].provider_name == "tavily"
    assert metrics.provider_metrics[0].calls == 1
    assert metrics.provider_metrics[0].failures == 1
    assert metrics.step_metrics[0].step_name == "clarification_validator"

    trace = service.run_trace(run_id=succeeded_run.run_id)
    assert trace is not None
    assert trace.run.run_id == succeeded_run.run_id
    assert len(trace.steps) == 1
    assert len(trace.audit_events) == 3
    assert len(trace.decision_timeline) == 3
    assert trace.decision_timeline[0].headline == "Destination Research checked web search"
    assert trace.decision_timeline[1].headline == "Destination Research finished"
    assert trace.decision_timeline[2].headline == "Coordinator routed work to Destination Research"


def test_observability_alerts_report_threshold_breaches(tmp_path):
    database_path = tmp_path / "alerts.db"
    settings = build_settings(database_url=f"sqlite+pysqlite:///{database_path}")
    engine = build_engine(settings)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260611_000006')"))

    session_factory = build_session_factory(engine)
    run_repository = PostgresWorkflowRunRepository(session_factory=session_factory)
    step_repository = PostgresWorkflowRunStepRepository(session_factory=session_factory)
    audit_repository = PostgresAuditEventRepository(session_factory=session_factory)
    audit_service = AuditService(repository=audit_repository)
    service = ObservabilityService(
        settings=settings,
        session_factory=session_factory,
        workflow_run_repository=run_repository,
        workflow_run_step_repository=step_repository,
        audit_repository=audit_repository,
        logger=get_logger("test.observability"),
    )

    request = build_request()
    now = datetime.utcnow()
    run_repository.save(
        WorkflowRun(
            run_id=str(uuid4()),
            trip_id=str(uuid4()),
            request=request,
            execution_mode=WorkflowExecutionMode.ASYNC,
            status=WorkflowRunStatus.DEAD_LETTERED,
            created_at=now - timedelta(minutes=6),
            updated_at=now - timedelta(minutes=4),
            retry_count=3,
        )
    )
    run_repository.save(
        WorkflowRun(
            run_id=str(uuid4()),
            trip_id=str(uuid4()),
            request=request,
            execution_mode=WorkflowExecutionMode.ASYNC,
            status=WorkflowRunStatus.RUNNING,
            created_at=now - timedelta(minutes=10),
            updated_at=now - timedelta(minutes=3),
            current_step="destination_research_agent",
        )
    )
    audit_service.record_event(
        event_type="tool_failed",
        provider_name="tavily",
        provider_endpoint="/search",
        status="execution_failed",
        payload={},
    )

    alerts = service.alerts_report()
    codes = {alert.code for alert in alerts.alerts}
    assert alerts.healthy is False
    assert "run_failure_rate_high" in codes
    assert "dead_letter_runs_present" in codes
    assert "provider_failures_high" in codes
    assert "stuck_runs_detected" in codes
