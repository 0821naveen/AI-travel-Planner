from __future__ import annotations

from logging import Logger
from typing import Optional

from src.agents.travel_planner.graph import TravelPlannerGraph
from src.agents.travel_planner.schemas import CreateTripResponse, TripRequest
from src.application.trips.use_cases import CreateTripUseCase, GetTripUseCase
from src.domain.trips.repositories import TripRepository
from src.services.audit_service import AuditService
from src.services.workflow_runtime_service import WorkflowRuntimeService


class TravelPlannerService:
    def __init__(
        self,
        *,
        repository: TripRepository,
        graph: TravelPlannerGraph,
        logger: Logger,
        audit_service: AuditService | None = None,
        workflow_runtime_service: WorkflowRuntimeService | None = None,
    ) -> None:
        self.graph = graph
        self.repository = repository
        self.logger = logger
        self.workflow_runtime_service = workflow_runtime_service
        self.create_trip_use_case = CreateTripUseCase(
            graph=self.graph,
            repository=self.repository,
            logger=self.logger,
            audit_service=audit_service,
        )
        self.get_trip_use_case = GetTripUseCase(repository=self.repository)

    def create_trip(self, request: TripRequest, *, run_id: str | None = None) -> CreateTripResponse:
        if self.workflow_runtime_service is not None:
            return self.workflow_runtime_service.execute_sync(request)
        return self.create_trip_use_case.execute(request, run_id=run_id)

    def get_trip(self, trip_id: str) -> Optional[CreateTripResponse]:
        return self.get_trip_use_case.execute(trip_id)
