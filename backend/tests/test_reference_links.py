from src.agents.travel_planner.nodes import (
    FoodRecommendationAgent,
    ItineraryPlanningAgent,
    StayRecommendationAgent,
)
from src.agents.travel_planner.schemas import (
    BudgetTier,
    ItineraryDayPlan,
    TravelerConstraints,
    TripPurpose,
    TripRequest,
)
from src.agents.travel_planner.state import PlannerContext


def build_request() -> TripRequest:
    return TripRequest(
        origin_city="Bengaluru",
        destination="Goa",
        start_date="2026-07-10",
        end_date="2026-07-12",
        traveler_count=2,
        trip_purpose=TripPurpose.LEISURE,
        total_budget=45000,
        budget_tier=BudgetTier.MID_RANGE,
        pace="balanced",
        interests=["food", "photography"],
        accommodation_preference="boutique hotel",
        transport_preference="cab",
        constraints=TravelerConstraints(),
    )


def test_itinerary_day_plan_remains_backward_compatible():
    day = ItineraryDayPlan(
        day_number=1,
        date="2026-07-10",
        theme="Arrival",
        morning="Arrive",
        afternoon="Explore",
        evening="Dinner",
        area="Panjim",
        transport_note="Take a cab",
        recommended_restaurant="Local favorite",
        signature_dishes=["Fish curry"],
        photo_spot="Riverfront",
        photo_timing="Golden hour",
        pace_level="balanced",
        estimated_daily_cost="Approx 9000",
        reasoning="Compatibility test",
    )

    assert day.restaurant_maps_url == ""
    assert day.restaurant_website_url == ""
    assert day.restaurant_review_video_urls == []
    assert day.photo_maps_url == ""
    assert day.photo_blog_urls == []
    assert day.photo_vlog_urls == []


def test_fallback_plans_include_reference_links():
    context = PlannerContext(trip_id="trip-links", request=build_request())

    itinerary = ItineraryPlanningAgent()._fallback_plan(context, "model unavailable")
    stay = StayRecommendationAgent()._fallback_plan(context, "model unavailable")
    food = FoodRecommendationAgent()._fallback_plan(context, "model unavailable")

    assert itinerary.days[0].restaurant_maps_url.startswith("https://")
    assert itinerary.days[0].restaurant_review_video_urls
    assert itinerary.days[0].photo_maps_url.startswith("https://")
    assert itinerary.days[0].photo_blog_urls
    assert itinerary.days[0].photo_vlog_urls
    assert stay.recommendations[0].booking_url.startswith("https://")
    assert stay.recommendations[0].maps_url.startswith("https://")
    assert food.recommendations[0].maps_url.startswith("https://")
    assert food.recommendations[0].review_video_urls


def test_food_recommendation_agent_uses_tripadvisor_summary_in_primary_path(monkeypatch):
    context = PlannerContext(trip_id="trip-food", request=build_request())
    context.itinerary_plan = ItineraryPlanningAgent()._fallback_plan(context, "seed itinerary")

    class FakeRegistry:
        def is_available(self, name: str) -> bool:
            return name in {"web_search", "tripadvisor_search", "json_completion"}

    class FakeToolResult:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeExecutor:
        registry = FakeRegistry()

        def execute(self, name: str, payload):
            if name == "web_search":
                return FakeToolResult(summary="General food research summary")
            if name == "tripadvisor_search":
                return FakeToolResult(
                    summary="Tripadvisor says Keventer's and Glenary's are top traveler picks.",
                    results=[],
                )
            if name == "json_completion":
                return FakeToolResult(
                    payload={
                        "summary": "Food plan synthesized from research and traveler reviews.",
                        "confidence": 0.79,
                        "recommendations": [
                            {
                                "day_number": 1,
                                "meal": "breakfast",
                                "venue_name": "Keventer's",
                                "area": "Darjeeling Mall Road",
                                "cuisine_type": "Cafe",
                                "price_level": "mid_range",
                                "dietary_fit": "Good for general travelers",
                                "why_fit": "Pairs well with the morning walk and local sightseeing.",
                                "maps_url": "https://maps.example/keventers",
                                "official_website": "https://keventers.example",
                                "review_video_urls": ["https://youtube.com/watch?v=abc123"],
                            }
                        ],
                    }
                )
            raise AssertionError(f"Unexpected tool call: {name}")

    monkeypatch.setattr("src.agents.travel_planner.nodes.build_tool_executor", lambda _context, _name: FakeExecutor())

    updated = FoodRecommendationAgent().run(context)

    assert updated.food_recommendation_plan is not None
    assert updated.food_recommendation_plan.summary == "Food plan synthesized from research and traveler reviews."
    assert (
        updated.food_recommendation_plan.traveler_review_summary
        == "Tripadvisor says Keventer's and Glenary's are top traveler picks."
    )
    assert updated.food_recommendation_plan.recommendations[0].venue_name == "Keventer's"
