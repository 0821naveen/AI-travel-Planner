from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from src.agents.travel_planner.schemas import (
    ClarificationCopilotRequest,
    ClarificationCopilotResponse,
    CreateTripResponse,
    TripRequest,
)
from src.application.admin.schemas import (
    AdminDashboardResponse,
    AdminTripListItemResponse,
    ApprovalDecisionRequest,
    TripReviewDetailResponse,
)
from src.application.audit.mappers import audit_event_response_from_record
from src.application.audit.schemas import AuditEventResponse
from src.application.auth.schemas import AuthSessionResponse, LoginRequest, RegisterUserRequest, UserProfileResponse
from src.application.jobs.schemas import PlannerJobResponse
from src.application.observability.schemas import AlertsResponse, ObservabilityMetricsResponse, RunTraceResponse
from src.application.trips.async_use_cases import CreateTripAsyncUseCase, GetJobUseCase
from src.application.workflows.mappers import workflow_run_response_from_record
from src.application.workflows.schemas import WorkflowRunResponse
from src.application.workflows.step_mappers import workflow_run_step_response_from_record
from src.application.workflows.step_schemas import WorkflowRunStepResponse
from src.bootstrap import (
    get_audit_service,
    get_auth_service,
    get_clarification_copilot_service,
    get_create_trip_async_use_case,
    get_observability_service,
    get_operator_review_service,
    get_readiness_service,
    get_travel_planner_service,
    get_workflow_runtime_service,
)
from src.bootstrap import (
    get_job_use_case as get_job_use_case_dependency,
)
from src.core.response_shaping import shape_trip_response
from src.core.security import ActorContext, ActorRole, require_roles
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.clarification_copilot_service import ClarificationCopilotService
from src.services.observability_service import ObservabilityService
from src.services.operator_review_service import OperatorReviewService
from src.services.readiness_service import ReadinessService
from src.services.travel_planner_service import TravelPlannerService
from src.services.workflow_runtime_service import WorkflowRuntimeService

router = APIRouter(prefix="/api")


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/readiness")
def readiness(
    readiness_service: ReadinessService = Depends(get_readiness_service),
) -> JSONResponse:
    report = readiness_service.readiness_report()
    return JSONResponse(content=report, status_code=200 if bool(report["healthy"]) else 503)


@router.get("/health/dependencies")
def dependencies_health(
    readiness_service: ReadinessService = Depends(get_readiness_service),
) -> dict[str, object]:
    return readiness_service.readiness_report()


@router.post("/auth/register", response_model=AuthSessionResponse)
def register_user(
    request: RegisterUserRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    return auth_service.register(request)


@router.post("/auth/login", response_model=AuthSessionResponse)
def login_user(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    return auth_service.login(request)


@router.get("/auth/me", response_model=UserProfileResponse)
def get_current_user(
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR, ActorRole.USER)),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserProfileResponse:
    if not actor.actor_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return auth_service.get_profile(actor.actor_id)


@router.post("/trips", response_model=CreateTripResponse)
def create_trip(
    http_request: Request,
    request: TripRequest,
    travel_planner_service: TravelPlannerService = Depends(get_travel_planner_service),
    audit_service: AuditService = Depends(get_audit_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR, ActorRole.USER)),
) -> CreateTripResponse:
    audit_service.record_event(
        event_type="request_received",
        request_id=http_request.state.request_id,
        actor_id=actor.actor_id,
        actor_role=actor.role.value,
        status="accepted",
        payload={"destination": request.destination, "mode": "sync"},
    )
    response = shape_trip_response(travel_planner_service.create_trip(request))
    audit_service.record_event(
        event_type="response_returned",
        request_id=http_request.state.request_id,
        trip_id=response.trip.trip_id,
        run_id=response.run_id,
        actor_id=actor.actor_id,
        actor_role=actor.role.value,
        status=response.trip.status.value,
        payload={"clarification_needed": response.clarification_needed},
    )
    return response


@router.post("/trips/async", response_model=PlannerJobResponse)
def create_trip_async(
    request: TripRequest,
    create_trip_async_use_case: CreateTripAsyncUseCase = Depends(get_create_trip_async_use_case),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR, ActorRole.USER)),
) -> PlannerJobResponse:
    return create_trip_async_use_case.execute(request)


@router.post("/clarification/copilot", response_model=ClarificationCopilotResponse)
def clarification_copilot(
    request: ClarificationCopilotRequest,
    clarification_copilot_service: ClarificationCopilotService = Depends(get_clarification_copilot_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR, ActorRole.USER)),
) -> ClarificationCopilotResponse:
    return clarification_copilot_service.next_turn(request)


@router.get("/trips/{trip_id}", response_model=CreateTripResponse)
def get_trip(
    trip_id: str,
    travel_planner_service: TravelPlannerService = Depends(get_travel_planner_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR, ActorRole.USER)),
) -> CreateTripResponse:
    trip = travel_planner_service.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return shape_trip_response(trip)


@router.get("/jobs/{job_id}", response_model=PlannerJobResponse)
def get_job(
    job_id: str,
    get_job_use_case: GetJobUseCase = Depends(get_job_use_case_dependency),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR, ActorRole.USER)),
) -> PlannerJobResponse:
    job = get_job_use_case.execute(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/admin/runs/{run_id}/audit", response_model=list[AuditEventResponse])
def get_run_audit_events(
    run_id: str,
    audit_service: AuditService = Depends(get_audit_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> list[AuditEventResponse]:
    return [audit_event_response_from_record(item) for item in audit_service.list_by_run_id(run_id)]


@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
def get_admin_dashboard(
    operator_review_service: OperatorReviewService = Depends(get_operator_review_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> AdminDashboardResponse:
    return operator_review_service.dashboard()


@router.get("/admin/review-queue", response_model=list[AdminTripListItemResponse])
def get_review_queue(
    operator_review_service: OperatorReviewService = Depends(get_operator_review_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> list[AdminTripListItemResponse]:
    return operator_review_service.review_queue()


@router.get("/admin/trips/{trip_id}/review", response_model=TripReviewDetailResponse)
def get_trip_review_detail(
    trip_id: str,
    operator_review_service: OperatorReviewService = Depends(get_operator_review_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> TripReviewDetailResponse:
    detail = operator_review_service.get_review_detail(trip_id=trip_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return detail


@router.post("/admin/trips/{trip_id}/approval", response_model=TripReviewDetailResponse)
def decide_trip_approval(
    trip_id: str,
    decision: ApprovalDecisionRequest,
    http_request: Request,
    operator_review_service: OperatorReviewService = Depends(get_operator_review_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> TripReviewDetailResponse:
    try:
        detail = operator_review_service.apply_approval_decision(
            trip_id=trip_id,
            decision=decision,
            actor=actor,
            request_id=http_request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return detail


@router.get("/admin/observability/metrics", response_model=ObservabilityMetricsResponse)
def get_observability_metrics(
    lookback_hours: Optional[int] = None,
    observability_service: ObservabilityService = Depends(get_observability_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> ObservabilityMetricsResponse:
    return observability_service.metrics_report(lookback_hours=lookback_hours)


@router.get("/admin/observability/alerts", response_model=AlertsResponse)
def get_observability_alerts(
    lookback_hours: Optional[int] = None,
    observability_service: ObservabilityService = Depends(get_observability_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> AlertsResponse:
    return observability_service.alerts_report(lookback_hours=lookback_hours)


@router.get("/admin/runs/{run_id}/trace", response_model=RunTraceResponse)
def get_run_trace(
    run_id: str,
    observability_service: ObservabilityService = Depends(get_observability_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> RunTraceResponse:
    trace = observability_service.run_trace(run_id=run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return trace


@router.get("/admin/runs", response_model=list[WorkflowRunResponse])
def get_recent_runs(
    limit: int = 20,
    workflow_runtime_service: WorkflowRuntimeService = Depends(get_workflow_runtime_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> list[WorkflowRunResponse]:
    return [
        workflow_run_response_from_record(item)
        for item in workflow_runtime_service.list_recent_runs(limit=max(1, min(limit, 100)))
    ]


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_run(
    run_id: str,
    workflow_runtime_service: WorkflowRuntimeService = Depends(get_workflow_runtime_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR, ActorRole.USER)),
) -> WorkflowRunResponse:
    run = workflow_runtime_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return workflow_run_response_from_record(run)


@router.post("/runs/{run_id}/cancel", response_model=WorkflowRunResponse)
def cancel_run(
    run_id: str,
    workflow_runtime_service: WorkflowRuntimeService = Depends(get_workflow_runtime_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> WorkflowRunResponse:
    run = workflow_runtime_service.cancel_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return workflow_run_response_from_record(run)


@router.post("/runs/{run_id}/rerun", response_model=WorkflowRunResponse)
def rerun_run(
    run_id: str,
    workflow_runtime_service: WorkflowRuntimeService = Depends(get_workflow_runtime_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR)),
) -> WorkflowRunResponse:
    run = workflow_runtime_service.rerun_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return workflow_run_response_from_record(run)


@router.get("/runs/{run_id}/steps", response_model=list[WorkflowRunStepResponse])
def get_run_steps(
    run_id: str,
    workflow_runtime_service: WorkflowRuntimeService = Depends(get_workflow_runtime_service),
    actor: ActorContext = Depends(require_roles(ActorRole.ADMIN, ActorRole.OPERATOR, ActorRole.USER)),
) -> list[WorkflowRunStepResponse]:
    return [workflow_run_step_response_from_record(item) for item in workflow_runtime_service.list_run_steps(run_id)]
