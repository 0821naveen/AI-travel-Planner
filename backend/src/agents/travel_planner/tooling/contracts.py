from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from src.agents.travel_planner.schemas import ResearchSource
from src.agents.travel_planner.tooling.base import ToolOutputBase


class WeatherLookupInput(BaseModel):
    location: str
    forecast_days: Optional[int] = None


class WeatherLookupOutput(ToolOutputBase):
    payload: dict[str, Any]


class WebSearchInput(BaseModel):
    queries: list[str]
    max_results: int = 4
    results_per_query: int = 3


class WebSearchOutput(ToolOutputBase):
    summary: str
    sources: list[ResearchSource]


class JsonCompletionOutput(ToolOutputBase):
    payload: dict[str, Any]


class GoogleHotelsInput(BaseModel):
    query: str
    check_in_date: str
    check_out_date: str
    adults: int = 2
    children: int = 0
    currency: str = "INR"
    gl: str = "in"
    hl: str = "en"


class GoogleHotelsProperty(BaseModel):
    name: str
    link: str = ""
    rate_per_night: str = ""
    total_rate: str = ""
    overall_rating: Optional[float] = None
    reviews: Optional[int] = None
    type: str = ""
    hotel_class: str = ""
    extracted_hotel_class: Optional[float] = None
    gps_coordinates: dict[str, Any] = Field(default_factory=dict)


class GoogleHotelsOutput(ToolOutputBase):
    summary: str
    properties: list[GoogleHotelsProperty]
    raw_payload: dict[str, Any]


class YouTubeVideoInput(BaseModel):
    video_id: str
    hl: str = "en"


class YouTubeVideoOutput(ToolOutputBase):
    title: str = ""
    channel_name: str = ""
    description: str = ""
    views: str = ""
    publish_date: str = ""
    likes: str = ""
    link: str = ""
    raw_payload: dict[str, Any]


class TripadvisorSearchInput(BaseModel):
    query: str
    location: str = ""
    hl: str = "en"


class TripadvisorResult(BaseModel):
    title: str
    link: str = ""
    rating: str = ""
    reviews: str = ""
    category: str = ""
    snippet: str = ""


class TripadvisorSearchOutput(ToolOutputBase):
    summary: str
    results: list[TripadvisorResult]
    raw_payload: dict[str, Any]


class GoogleFlightsInput(BaseModel):
    departure_id: str
    arrival_id: str
    outbound_date: str
    return_date: str
    adults: int = 1
    children: int = 0
    currency: str = "INR"
    hl: str = "en"
    gl: str = "in"
    travel_class: int = 1


class GoogleFlightsBestFlight(BaseModel):
    airline: str = ""
    price: str = ""
    total_duration: str = ""
    departure_airport: str = ""
    arrival_airport: str = ""


class GoogleFlightsOutput(ToolOutputBase):
    summary: str
    best_flights: list[GoogleFlightsBestFlight]
    raw_payload: dict[str, Any]


class FlightScheduleLookupInput(BaseModel):
    origin_city: str
    destination_city: str
    flight_date: str


class FlightScheduleOption(BaseModel):
    airline: str = ""
    flight_number: str = ""
    departure_airport: str = ""
    arrival_airport: str = ""
    scheduled_departure: str = ""
    scheduled_arrival: str = ""
    flight_status: str = ""


class FlightScheduleLookupOutput(ToolOutputBase):
    summary: str
    origin_airports: list[str]
    destination_airports: list[str]
    flights: list[FlightScheduleOption]
    raw_payload: dict[str, Any]


def sanitize_untrusted_text(value: str) -> str:
    lowered = value.lower()
    blocked_patterns = [
        "ignore previous instructions",
        "system prompt",
        "developer message",
        "tool instructions",
        "<script",
        "</script>",
    ]
    if any(pattern in lowered for pattern in blocked_patterns):
        return "[sanitized-untrusted-content]"
    return value
