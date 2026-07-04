from __future__ import annotations

from dataclasses import dataclass
from logging import Logger

from fastapi import Depends, Request
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.agents.travel_planner.graph import TravelPlannerGraph
from src.agents.travel_planner.multi_agent.runtime import CoordinatorRuntime
from src.application.trips.async_use_cases import CreateTripAsyncUseCase, GetJobUseCase
from src.core.config import Settings, get_settings
from src.core.logging import get_logger
from src.core.security import RateLimiter, build_rate_limiter
from src.db.session import build_engine, build_session_factory
from src.messaging.redis_queue import build_workflow_queue
from src.persistence.postgres.audit_repository import PostgresAuditEventRepository
from src.persistence.postgres.job_repository import PostgresJobRepository
from src.persistence.postgres.trip_repository import PostgresTripRepository
from src.persistence.postgres.user_repository import PostgresUserRepository
from src.persistence.postgres.workflow_run_repository import PostgresWorkflowRunRepository
from src.persistence.postgres.workflow_run_step_repository import PostgresWorkflowRunStepRepository
from src.providers.factory import build_clients
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.clarification_copilot_service import ClarificationCopilotService
from src.services.observability_service import ObservabilityService
from src.services.operator_review_service import OperatorReviewService
from src.services.readiness_service import ReadinessService
from src.services.travel_planner_service import TravelPlannerService
from src.services.workflow_runtime_service import WorkflowRuntimeService


@dataclass
class ApplicationContainer:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    graph: TravelPlannerGraph
    coordinator_runtime: CoordinatorRuntime
    trip_repository: PostgresTripRepository
    job_repository: PostgresJobRepository
    workflow_run_repository: PostgresWorkflowRunRepository
    workflow_run_step_repository: PostgresWorkflowRunStepRepository
    audit_repository: PostgresAuditEventRepository
    user_repository: PostgresUserRepository
    audit_service: AuditService
    auth_service: AuthService
    clarification_copilot_service: ClarificationCopilotService
    operator_review_service: OperatorReviewService
    travel_planner_service: TravelPlannerService
    workflow_queue: object
    workflow_runtime_service: WorkflowRuntimeService
    readiness_service: ReadinessService
    observability_service: ObservabilityService
    create_trip_async_use_case: CreateTripAsyncUseCase
    get_job_use_case: GetJobUseCase
    rate_limiter: RateLimiter

    def shutdown(self) -> None:
        self.engine.dispose()

    def assert_startup_ready(self) -> None:
        if self.settings.app.environment == "test":
            return
        self.readiness_service.assert_startup_ready()


def create_container(settings: Settings | None = None) -> ApplicationContainer:
    resolved_settings = settings or get_settings()
    engine = build_engine(resolved_settings)
    session_factory = build_session_factory(engine)
    graph = TravelPlannerGraph()
    coordinator_runtime = CoordinatorRuntime()
    trip_repository = PostgresTripRepository(session_factory=session_factory)
    job_repository = PostgresJobRepository(session_factory=session_factory)
    workflow_run_repository = PostgresWorkflowRunRepository(session_factory=session_factory)
    workflow_run_step_repository = PostgresWorkflowRunStepRepository(session_factory=session_factory)
    audit_repository = PostgresAuditEventRepository(session_factory=session_factory)
    user_repository = PostgresUserRepository(session_factory=session_factory)
    audit_service = AuditService(repository=audit_repository)
    auth_service = AuthService(repository=user_repository, settings=resolved_settings)
    tavily_client, _, openai_client, _, _ = build_clients()
    clarification_copilot_service = ClarificationCopilotService(
        tavily_client=tavily_client,
        openai_client=openai_client,
    )
    operator_review_service = OperatorReviewService(repository=trip_repository, audit_service=audit_service)
    workflow_queue = build_workflow_queue(resolved_settings)
    workflow_runtime_service = WorkflowRuntimeService(
        settings=resolved_settings,
        graph=graph,
        coordinator_runtime=coordinator_runtime,
        trip_repository=trip_repository,
        job_repository=job_repository,
        workflow_run_repository=workflow_run_repository,
        workflow_run_step_repository=workflow_run_step_repository,
        audit_service=audit_service,
        workflow_queue=workflow_queue,
        logger=get_logger("travel_planner.workflow_runtime"),
    )
    readiness_service = ReadinessService(
        settings=resolved_settings,
        engine=engine,
        workflow_queue=workflow_queue,
    )
    observability_service = ObservabilityService(
        settings=resolved_settings,
        session_factory=session_factory,
        workflow_run_repository=workflow_run_repository,
        workflow_run_step_repository=workflow_run_step_repository,
        audit_repository=audit_repository,
        logger=get_logger("travel_planner.observability"),
    )
    logger: Logger = get_logger("travel_planner.service")
    travel_planner_service = TravelPlannerService(
        repository=trip_repository,
        graph=graph,
        logger=logger,
        audit_service=audit_service,
        workflow_runtime_service=workflow_runtime_service,
    )
    create_trip_async_use_case = CreateTripAsyncUseCase(
        workflow_runtime_service=workflow_runtime_service,
        audit_service=audit_service,
    )
    get_job_use_case = GetJobUseCase(job_repository=job_repository)
    rate_limiter = build_rate_limiter(resolved_settings)

    return ApplicationContainer(
        settings=resolved_settings,
        engine=engine,
        session_factory=session_factory,
        graph=graph,
        coordinator_runtime=coordinator_runtime,
        trip_repository=trip_repository,
        job_repository=job_repository,
        workflow_run_repository=workflow_run_repository,
        workflow_run_step_repository=workflow_run_step_repository,
        audit_repository=audit_repository,
        user_repository=user_repository,
        audit_service=audit_service,
        auth_service=auth_service,
        clarification_copilot_service=clarification_copilot_service,
        operator_review_service=operator_review_service,
        travel_planner_service=travel_planner_service,
        workflow_queue=workflow_queue,
        workflow_runtime_service=workflow_runtime_service,
        readiness_service=readiness_service,
        observability_service=observability_service,
        create_trip_async_use_case=create_trip_async_use_case,
        get_job_use_case=get_job_use_case,
        rate_limiter=rate_limiter,
    )


def get_container(request: Request) -> ApplicationContainer:
    return request.app.state.container


def get_travel_planner_service(
    container: ApplicationContainer = Depends(get_container),
) -> TravelPlannerService:
    return container.travel_planner_service


def get_create_trip_async_use_case(
    container: ApplicationContainer = Depends(get_container),
) -> CreateTripAsyncUseCase:
    return container.create_trip_async_use_case


def get_job_use_case(
    container: ApplicationContainer = Depends(get_container),
) -> GetJobUseCase:
    return container.get_job_use_case


def get_audit_service(
    container: ApplicationContainer = Depends(get_container),
) -> AuditService:
    return container.audit_service


def get_auth_service(
    container: ApplicationContainer = Depends(get_container),
) -> AuthService:
    return container.auth_service


def get_clarification_copilot_service(
    container: ApplicationContainer = Depends(get_container),
) -> ClarificationCopilotService:
    return container.clarification_copilot_service


def get_operator_review_service(
    container: ApplicationContainer = Depends(get_container),
) -> OperatorReviewService:
    return container.operator_review_service


def get_workflow_runtime_service(
    container: ApplicationContainer = Depends(get_container),
) -> WorkflowRuntimeService:
    return container.workflow_runtime_service


def get_readiness_service(
    container: ApplicationContainer = Depends(get_container),
) -> ReadinessService:
    return container.readiness_service


def get_observability_service(
    container: ApplicationContainer = Depends(get_container),
) -> ObservabilityService:
    return container.observability_service
