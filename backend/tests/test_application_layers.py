from __future__ import annotations

from src.agents.travel_planner.schemas import BudgetTier, TravelerConstraints, TripPurpose, TripRequest, TripStatus
from src.agents.travel_planner.state import PlannerContext
from src.application.trips.use_cases import CreateTripUseCase
from src.core.logging import get_logger
from src.persistence.memory.trip_repository import InMemoryTripRepository


class FakeGraph:
    def bootstrap_trip(self, trip_id: str, request: TripRequest, *, run_id: str | None = None) -> PlannerContext:
        return PlannerContext(
            trip_id=trip_id,
            request=request,
            run_id=run_id,
            status=TripStatus.RESEARCH_READY,
            route_trace=["clarification_validator", "research_signal_agent"],
        )


def build_request():
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


def test_create_trip_use_case_persists_record():
    repository = InMemoryTripRepository()
    use_case = CreateTripUseCase(graph=FakeGraph(), repository=repository, logger=get_logger("test"))

    response = use_case.execute(build_request())
    stored = repository.get(response.trip.trip_id)

    assert stored is not None
    assert stored.trip_id == response.trip.trip_id
    assert stored.status == TripStatus.RESEARCH_READY
