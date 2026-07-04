from pydantic import BaseModel

from src.agents.travel_planner.schemas import BudgetTier, TravelerConstraints, TripPurpose, TripRequest, TripStatus
from src.agents.travel_planner.state import PlannerContext
from src.agents.travel_planner.tooling.base import (
    JsonCompletionInput,
    ToolAuthMethod,
    ToolAuthorizationError,
    ToolMetadata,
    ToolOutputBase,
    ToolSideEffectLevel,
    ToolUnavailableError,
)
from src.agents.travel_planner.tooling.contracts import (
    FlightScheduleLookupInput,
    GoogleFlightsInput,
    GoogleHotelsInput,
    TripadvisorSearchInput,
    YouTubeVideoInput,
)
from src.agents.travel_planner.tooling.registry import ToolExecutor, ToolRegistry
from src.agents.travel_planner.tooling.search_tools import SerpApiGoogleFlightsTool, SerpApiTripadvisorTool
from src.agents.travel_planner.tooling.travel_tools import (
    AviationstackFlightScheduleTool,
    SerpApiGoogleHotelsTool,
    SerpApiYouTubeVideoTool,
)


class EchoOutput(ToolOutputBase):
    developer_prompt: str
    user_prompt: str


class EchoTool:
    name = "echo"
    metadata = ToolMetadata(
        name="echo",
        description="Echo tool for testing",
        allowed_agents=("test_agent",),
        provider_name="test-provider",
        provider_endpoint="echo",
        auth_method=ToolAuthMethod.NONE,
        timeout_seconds=1,
        retry_policy="none",
        rate_limit_per_minute=100,
        side_effect_level=ToolSideEffectLevel.READ_ONLY,
        input_model=JsonCompletionInput,
        output_model=EchoOutput,
    )

    def is_available(self) -> bool:
        return True

    def execute(self, payload: JsonCompletionInput) -> EchoOutput:
        return EchoOutput(
            developer_prompt=payload.developer_prompt,
            user_prompt=payload.user_prompt,
        )


class OfflineTool:
    name = "offline"
    metadata = ToolMetadata(
        name="offline",
        description="Offline test tool",
        allowed_agents=("test_agent",),
        provider_name="test-provider",
        provider_endpoint="offline",
        auth_method=ToolAuthMethod.NONE,
        timeout_seconds=1,
        retry_policy="none",
        rate_limit_per_minute=100,
        side_effect_level=ToolSideEffectLevel.READ_ONLY,
        input_model=JsonCompletionInput,
        output_model=EchoOutput,
    )

    def is_available(self) -> bool:
        return False

    def execute(self, payload: JsonCompletionInput):
        raise AssertionError("Should not execute unavailable tools")


class InvalidOutput(BaseModel):
    ok: bool = True


class WrongOutputTool:
    name = "wrong-output"
    metadata = ToolMetadata(
        name="wrong-output",
        description="Returns an invalid output model for testing",
        allowed_agents=("test_agent",),
        provider_name="test-provider",
        provider_endpoint="wrong-output",
        auth_method=ToolAuthMethod.NONE,
        timeout_seconds=1,
        retry_policy="none",
        rate_limit_per_minute=100,
        side_effect_level=ToolSideEffectLevel.READ_ONLY,
        input_model=JsonCompletionInput,
        output_model=EchoOutput,
    )

    def is_available(self) -> bool:
        return True

    def execute(self, payload: JsonCompletionInput) -> InvalidOutput:
        return InvalidOutput()


def build_context() -> PlannerContext:
    return PlannerContext(
        trip_id="trip-1",
        run_id="run-1",
        request=TripRequest(
            origin_city="Bengaluru",
            destination="Mysuru",
            start_date="2026-05-10",
            end_date="2026-05-12",
            traveler_count=2,
            trip_purpose=TripPurpose.LEISURE,
            total_budget=12000,
            budget_tier=BudgetTier.MID_RANGE,
            pace="balanced",
            interests=["food"],
            constraints=TravelerConstraints(),
        ),
        status=TripStatus.DRAFT,
    )


def test_tool_executor_routes_payload_to_named_tool():
    executor = ToolExecutor(ToolRegistry([EchoTool()]), context=build_context(), agent_name="test_agent")

    result = executor.execute(
        "echo",
        JsonCompletionInput(developer_prompt="system", user_prompt="user"),
    )

    assert result.developer_prompt == "system"
    assert result.user_prompt == "user"
    assert executor.context.short_term_memory["tool_budget"]["tool_calls"] == 1
    assert executor.context.tool_audit_log[0]["run_id"] == "run-1"


def test_tool_executor_rejects_unavailable_tools():
    executor = ToolExecutor(ToolRegistry([OfflineTool()]), context=build_context(), agent_name="test_agent")

    try:
        executor.execute("offline", JsonCompletionInput(developer_prompt="a", user_prompt="b"))
    except ToolUnavailableError as exc:
        assert "offline" in str(exc)
    else:
        raise AssertionError("Unavailable tool execution should fail")


def test_tool_executor_rejects_unauthorized_agent():
    executor = ToolExecutor(ToolRegistry([EchoTool()]), context=build_context(), agent_name="wrong_agent")

    try:
        executor.execute("echo", JsonCompletionInput(developer_prompt="a", user_prompt="b"))
    except ToolAuthorizationError as exc:
        assert "wrong_agent" in str(exc)
    else:
        raise AssertionError("Unauthorized tool execution should fail")


class FakeSerpApiClient:
    def google_flights(self, **kwargs):
        return {
            "best_flights": [
                {
                    "price": "₹12,400",
                    "total_duration": "5 hr 20 min",
                    "flights": [
                        {
                            "airline": "IndiGo",
                            "departure_airport": {"name": "Kempegowda International Airport"},
                            "arrival_airport": {"name": "Bagdogra Airport"},
                        }
                    ],
                }
            ]
        }

    def google_hotels(self, **kwargs):
        return {
            "properties": [
                {
                    "name": "Summit Swiss Heritage Hotel",
                    "link": "https://example.com/hotel",
                    "rate_per_night": "₹6,500",
                    "overall_rating": 4.2,
                    "reviews": 812,
                }
            ]
        }

    def tripadvisor_search(self, **kwargs):
        return {
            "results": [
                {
                    "title": "Keventer's",
                    "link": "https://tripadvisor.example/keventers",
                    "rating": "4.5",
                    "reviews": "1024",
                    "category": "Cafe",
                    "snippet": "Popular breakfast stop with Kanchenjunga views.",
                }
            ]
        }

    def youtube_video(self, **kwargs):
        return {
            "video_details": {
                "title": "Best Food in Darjeeling",
                "channel_name": "Travel Vlogs India",
                "description": "Short review of iconic food stops.",
                "views": "120000",
                "published": "2026-01-04",
                "likes": "5300",
            }
        }


class FakeAviationstackClient:
    def airports(self, search: str):
        if search == "Bengaluru":
            return {"data": [{"iata_code": "BLR"}]}
        return {"data": [{"iata_code": "IXB"}]}

    def flights(self, **kwargs):
        return {
            "data": [
                {
                    "flight_status": "scheduled",
                    "flight": {"number": "6E 123"},
                    "airline": {"name": "IndiGo"},
                    "departure": {"airport": "Kempegowda International Airport", "scheduled": "2026-12-10T07:00:00+05:30"},
                    "arrival": {"airport": "Bagdogra Airport", "scheduled": "2026-12-10T10:15:00+05:30"},
                }
            ]
        }


def test_serpapi_google_flights_tool_maps_best_flight_summary():
    tool = SerpApiGoogleFlightsTool(FakeSerpApiClient())

    result = tool.execute(
        GoogleFlightsInput(
            departure_id="BLR",
            arrival_id="IXB",
            outbound_date="2026-12-10",
            return_date="2026-12-15",
        )
    )

    assert result.summary == "IndiGo | ₹12,400 | 5 hr 20 min"
    assert result.best_flights[0].departure_airport == "Kempegowda International Airport"
    assert result.best_flights[0].arrival_airport == "Bagdogra Airport"


def test_serpapi_google_hotels_tool_maps_property_summary():
    tool = SerpApiGoogleHotelsTool(FakeSerpApiClient())

    result = tool.execute(
        GoogleHotelsInput(
            query="darjeeling hotels",
            check_in_date="2026-12-10",
            check_out_date="2026-12-15",
        )
    )

    assert result.summary == "Summit Swiss Heritage Hotel | ₹6,500"
    assert result.properties[0].link == "https://example.com/hotel"
    assert result.properties[0].overall_rating == 4.2


def test_tripadvisor_tool_maps_traveler_context():
    tool = SerpApiTripadvisorTool(FakeSerpApiClient())

    result = tool.execute(TripadvisorSearchInput(query="darjeeling cafes", location="Darjeeling"))

    assert result.summary == "Keventer's | 4.5 | Cafe"
    assert result.results[0].title == "Keventer's"
    assert result.results[0].snippet == "Popular breakfast stop with Kanchenjunga views."


def test_youtube_video_tool_maps_video_details():
    tool = SerpApiYouTubeVideoTool(FakeSerpApiClient())

    result = tool.execute(YouTubeVideoInput(video_id="abc123"))

    assert result.title == "Best Food in Darjeeling"
    assert result.channel_name == "Travel Vlogs India"
    assert result.link == "https://www.youtube.com/watch?v=abc123"


def test_aviationstack_tool_maps_airports_and_flights():
    tool = AviationstackFlightScheduleTool(FakeAviationstackClient())

    result = tool.execute(
        FlightScheduleLookupInput(
            origin_city="Bengaluru",
            destination_city="Bagdogra",
            flight_date="2026-12-10",
        )
    )

    assert result.origin_airports == ["BLR"]
    assert result.destination_airports == ["IXB"]
    assert result.summary == "IndiGo 6E 123 | scheduled"
    assert result.flights[0].departure_airport == "Kempegowda International Airport"
