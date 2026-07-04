from src.agents.travel_planner.multi_agent.coordinator import CoordinatorAgent
from src.agents.travel_planner.multi_agent.runtime import CoordinatorRuntime
from src.agents.travel_planner.multi_agent.schemas import AgentRole
from src.agents.travel_planner.multi_agent.topology import (
    build_default_agent_specs,
    build_initial_coordination_ledger,
    delegation_allowed,
)
from src.agents.travel_planner.schemas import (
    BudgetTier,
    ItineraryDayPlan,
    ItineraryPlan,
    TravelerConstraints,
    TripPurpose,
    TripRequest,
)
from src.agents.travel_planner.state import PlannerContext


def build_request(**overrides) -> TripRequest:
    payload = {
        "origin_city": "Bengaluru",
        "destination": "Goa",
        "start_date": "2026-07-10",
        "end_date": "2026-07-14",
        "traveler_count": 2,
        "trip_purpose": TripPurpose.LEISURE,
        "total_budget": 45000,
        "budget_tier": BudgetTier.MID_RANGE,
        "pace": "balanced",
        "interests": ["food", "beaches", "photography"],
        "accommodation_preference": "boutique hotel",
        "transport_preference": "cab",
        "constraints": TravelerConstraints(),
    }
    payload.update(overrides)
    return TripRequest(**payload)


def test_default_agent_specs_define_controlled_delegation():
    specs = build_default_agent_specs()

    assert AgentRole.COORDINATOR in specs
    assert AgentRole.BUDGET in specs
    assert delegation_allowed(AgentRole.COORDINATOR, AgentRole.ITINERARY)
    assert not delegation_allowed(AgentRole.FOOD, AgentRole.GOVERNANCE)


def test_initial_coordination_ledger_matches_repo_artifacts():
    ledger = build_initial_coordination_ledger("trip-123", build_request())

    task_ids = [task.task_id for task in ledger.task_board]
    deliverables = {task.deliverable_key for task in ledger.task_board}

    assert ledger.objective.trip_id == "trip-123"
    assert ledger.active_role == AgentRole.COORDINATOR
    assert "draft_itinerary" in task_ids
    assert "critique_plan" in task_ids
    assert "itinerary_plan" in deliverables
    assert "review_assessment" in deliverables


def test_coordinator_assigns_first_specialist_task():
    request = build_request()
    ledger = build_initial_coordination_ledger("trip-456", request)
    context = PlannerContext(trip_id="trip-456", request=request)

    decision = CoordinatorAgent().run(ledger, context)

    assert decision.next_role == AgentRole.CLARIFICATION
    assert decision.task_id == "clarify_request"


def test_runtime_progresses_trip_with_custom_coordinator():
    runtime = CoordinatorRuntime()

    result = runtime.bootstrap_trip("trip-999", build_request())

    context = result["context"]
    ledger = result["ledger"]
    assert context.destination_research is not None
    assert context.itinerary_plan is not None
    assert context.review_assessment is not None
    assert ledger.message_log
    assert result["terminal_reason"] is not None


def test_coordinator_releases_parallel_specialist_batch_after_itinerary():
    request = build_request()
    ledger = build_initial_coordination_ledger("trip-par", request)
    for task_id in ["clarify_request", "research_destination", "draft_itinerary"]:
        task = next(task for task in ledger.task_board if task.task_id == task_id)
        task.status = task.status.COMPLETED
    context = PlannerContext(trip_id="trip-par", request=request)
    context.itinerary_plan = ItineraryPlan(
        destination=request.destination,
        summary="Seed itinerary",
        days=[
            ItineraryDayPlan(
                day_number=1,
                date=request.start_date,
                theme="Arrival",
                morning="Arrive",
                afternoon="Explore",
                evening="Dinner",
                area=request.destination,
                transport_note="Use local transport",
                recommended_restaurant="Local favorite",
                signature_dishes=["Regional signature dish"],
                photo_spot="Scenic lookout",
                photo_timing="Golden hour",
                pace_level=request.pace,
                estimated_daily_cost="Approx 9000",
                reasoning="Seed artifact for scheduler test",
            )
        ],
        budget_fit_note="Seed",
    )

    decision = CoordinatorAgent().run(ledger, context)

    assert set(decision.next_roles) == {
        AgentRole.STAY,
        AgentRole.TRANSPORT,
        AgentRole.FOOD,
        AgentRole.SAFETY,
    }
    assert decision.is_parallel_batch
