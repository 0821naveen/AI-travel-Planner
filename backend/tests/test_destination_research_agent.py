from __future__ import annotations

from src.agents.travel_planner.nodes import DestinationResearchAgent
from src.agents.travel_planner.schemas import (
    BudgetTier,
    TravelerConstraints,
    TripPurpose,
    TripRequest,
)
from src.agents.travel_planner.state import PlannerContext
from src.agents.travel_planner.tooling.contracts import GoogleFlightsBestFlight, GoogleFlightsOutput


class _FakeRegistry:
    def is_available(self, tool_name: str) -> bool:
        return tool_name == "google_flights_search"


class _RecordingExecutor:
    def __init__(self) -> None:
        self.registry = _FakeRegistry()
        self.calls: list[tuple[str, object]] = []

    def execute(self, tool_name: str, payload):
        self.calls.append((tool_name, payload))
        return GoogleFlightsOutput(
            summary="IndiGo | ₹12,400 | 5 hr 20 min",
            best_flights=[
                GoogleFlightsBestFlight(
                    airline="IndiGo",
                    price="₹12,400",
                    total_duration="5 hr 20 min",
                    departure_airport="Chennai International Airport",
                    arrival_airport="Manohar International Airport",
                )
            ],
            raw_payload={},
        )


def _build_context(origin_city: str = "Chennai", destination: str = "Goa") -> PlannerContext:
    return PlannerContext(
        trip_id="trip-flight-codes",
        request=TripRequest(
            origin_city=origin_city,
            destination=destination,
            start_date="2026-06-14",
            end_date="2026-06-17",
            traveler_count=1,
            trip_purpose=TripPurpose.LEISURE,
            total_budget=20000,
            budget_tier=BudgetTier.MID_RANGE,
            pace="balanced",
            interests=["beach"],
            constraints=TravelerConstraints(),
        ),
    )


def test_destination_research_agent_uses_resolved_airport_codes_for_google_flights():
    agent = DestinationResearchAgent()
    executor = _RecordingExecutor()

    result = agent._gather_flight_inventory(_build_context(), executor)

    assert len(executor.calls) == 1
    tool_name, payload = executor.calls[0]
    assert tool_name == "google_flights_search"
    assert payload.departure_id == "MAA"
    assert payload.arrival_id == "GOX"
    assert result["origin_airports"] == ["MAA"]
    assert result["destination_airports"] == ["GOX", "GOI"]


def test_destination_research_agent_skips_google_flights_when_airport_resolution_fails():
    agent = DestinationResearchAgent()
    executor = _RecordingExecutor()

    result = agent._gather_flight_inventory(_build_context(origin_city="Unknown Origin"), executor)

    assert executor.calls == []
    assert "could not be resolved" in result["summary"]
