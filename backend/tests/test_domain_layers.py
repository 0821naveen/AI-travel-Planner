import pytest

from src.agents.travel_planner.schemas import BudgetTier, TravelerConstraints, TripPurpose, TripRequest
from src.domain.trips.policies import ClarificationPolicy
from src.domain.trips.services import TripResearchSignalService


def build_request(**overrides):
    payload = {
        "origin_city": "Bengaluru",
        "destination": "Mysuru",
        "start_date": "2026-05-10",
        "end_date": "2026-05-12",
        "traveler_count": 2,
        "trip_purpose": TripPurpose.LEISURE,
        "total_budget": 12000,
        "budget_tier": BudgetTier.MID_RANGE,
        "pace": "balanced",
        "interests": ["food", "culture"],
        "accommodation_preference": "hotel",
        "transport_preference": "train",
        "constraints": TravelerConstraints(),
    }
    payload.update(overrides)
    return TripRequest(**payload)


def test_clarification_policy_generates_expected_questions():
    request = build_request(
        interests=[],
        accommodation_preference=None,
        transport_preference=None,
    )
    questions = ClarificationPolicy().build_questions(request)

    keys = [question.key for question in questions]
    assert "interests" in keys
    assert "accommodation_preference" in keys
    assert "transport_preference" in keys
    assert "special_constraints" in keys


def test_research_signal_service_builds_trip_signals():
    request = build_request(total_budget=9000, start_date="2026-05-10", end_date="2026-05-12")

    signals = TripResearchSignalService().build(request)

    assert signals["days"] == 3
    assert signals["budget_per_day"] == 3000.0
    assert signals["budget_tier"] == "mid_range"


def test_trip_request_normalizes_and_validates_dates():
    request = build_request(
        origin_city="  Bengaluru ",
        destination=" Mysuru ",
        pace=" Balanced ",
        interests=[" food ", "food", " history "],
        constraints=TravelerConstraints(notes=" reach me at test@example.com "),
    )

    assert request.origin_city == "Bengaluru"
    assert request.destination == "Mysuru"
    assert request.pace == "balanced"
    assert request.interests == ["food", "history"]

    with pytest.raises(ValueError):
        build_request(start_date="2026-05-12", end_date="2026-05-10")
