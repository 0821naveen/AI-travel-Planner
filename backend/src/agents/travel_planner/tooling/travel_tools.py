from __future__ import annotations

from typing import Any

from src.agents.travel_planner.tooling.base import (
    ToolAuthMethod,
    ToolMetadata,
    ToolSideEffectLevel,
    ToolUnavailableError,
    ToolUsage,
)
from src.agents.travel_planner.tooling.airports import resolve_known_airports
from src.agents.travel_planner.tooling.contracts import (
    FlightScheduleLookupInput,
    FlightScheduleLookupOutput,
    FlightScheduleOption,
    GoogleHotelsInput,
    GoogleHotelsOutput,
    GoogleHotelsProperty,
    WeatherLookupInput,
    WeatherLookupOutput,
    YouTubeVideoInput,
    YouTubeVideoOutput,
)
from src.core.config import get_settings
from src.providers.search import SerpApiClient
from src.providers.travel import AviationstackClient, WeatherApiClient


class WeatherLookupTool:
    name = "weather_lookup"
    metadata = ToolMetadata(
        name="weather_lookup",
        description="Fetches current weather or near-term forecasts for a destination.",
        allowed_agents=("destination_research_agent",),
        provider_name="weatherapi",
        provider_endpoint="forecast/current",
        auth_method=ToolAuthMethod.API_KEY,
        timeout_seconds=10,
        retry_policy="single_attempt",
        rate_limit_per_minute=60,
        side_effect_level=ToolSideEffectLevel.EXTERNAL_READ,
        input_model=WeatherLookupInput,
        output_model=WeatherLookupOutput,
    )

    def __init__(self, client: WeatherApiClient | None) -> None:
        self.client = client

    def is_available(self) -> bool:
        return self.client is not None

    def execute(self, payload: WeatherLookupInput) -> WeatherLookupOutput:
        if self.client is None:
            raise ToolUnavailableError("Weather API key is not configured.")
        response = (
            self.client.forecast(payload.location, payload.forecast_days)
            if payload.forecast_days is not None
            else self.client.current(payload.location)
        )
        return WeatherLookupOutput(payload=response, usage=ToolUsage())


class SerpApiGoogleHotelsTool:
    name = "google_hotels_search"
    metadata = ToolMetadata(
        name="google_hotels_search",
        description="Fetches structured Google Hotels results through SerpApi for hotel enrichment.",
        allowed_agents=("stay_recommendation_agent",),
        provider_name="serpapi",
        provider_endpoint="google_hotels",
        auth_method=ToolAuthMethod.API_KEY,
        timeout_seconds=20,
        retry_policy="retry_once",
        rate_limit_per_minute=20,
        side_effect_level=ToolSideEffectLevel.EXTERNAL_READ,
        input_model=GoogleHotelsInput,
        output_model=GoogleHotelsOutput,
    )

    def __init__(self, client: SerpApiClient | None) -> None:
        self.client = client

    def is_available(self) -> bool:
        return self.client is not None

    def execute(self, payload: GoogleHotelsInput) -> GoogleHotelsOutput:
        if self.client is None:
            raise ToolUnavailableError("SerpApi key is not configured.")
        response = self.client.google_hotels(
            query=payload.query,
            check_in_date=payload.check_in_date,
            check_out_date=payload.check_out_date,
            adults=payload.adults,
            children=payload.children,
            currency=payload.currency,
            gl=payload.gl,
            hl=payload.hl,
        )
        properties: list[GoogleHotelsProperty] = []
        for item in response.get("properties", [])[: get_settings().provider_runtime.serpapi_hotel_limit]:
            properties.append(
                GoogleHotelsProperty(
                    name=str(item.get("name") or "Unnamed property").strip(),
                    link=str(item.get("link") or item.get("property_token") or "").strip(),
                    rate_per_night=str(item.get("rate_per_night") or "").strip(),
                    total_rate=str(item.get("total_rate") or "").strip(),
                    overall_rating=float(item["overall_rating"]) if item.get("overall_rating") is not None else None,
                    reviews=int(item["reviews"]) if item.get("reviews") is not None else None,
                    type=str(item.get("type") or "").strip(),
                    hotel_class=str(item.get("hotel_class") or "").strip(),
                    extracted_hotel_class=float(item["extracted_hotel_class"])
                    if item.get("extracted_hotel_class") is not None
                    else None,
                    gps_coordinates=item.get("gps_coordinates") or {},
                )
            )
        summary_parts = [
            f"{prop.name} | {prop.rate_per_night or prop.total_rate or 'Rate unavailable'}"
            for prop in properties[:3]
        ]
        return GoogleHotelsOutput(
            summary="; ".join(summary_parts) if summary_parts else "No hotel properties returned.",
            properties=properties,
            raw_payload=response,
            usage=ToolUsage(),
        )


class SerpApiYouTubeVideoTool:
    name = "youtube_video_details"
    metadata = ToolMetadata(
        name="youtube_video_details",
        description="Fetches structured YouTube video details through SerpApi for review enrichment.",
        allowed_agents=("food_recommendation_agent", "itinerary_planning_agent"),
        provider_name="serpapi",
        provider_endpoint="youtube_video",
        auth_method=ToolAuthMethod.API_KEY,
        timeout_seconds=20,
        retry_policy="retry_once",
        rate_limit_per_minute=20,
        side_effect_level=ToolSideEffectLevel.EXTERNAL_READ,
        input_model=YouTubeVideoInput,
        output_model=YouTubeVideoOutput,
    )

    def __init__(self, client: SerpApiClient | None) -> None:
        self.client = client

    def is_available(self) -> bool:
        return self.client is not None

    def execute(self, payload: YouTubeVideoInput) -> YouTubeVideoOutput:
        if self.client is None:
            raise ToolUnavailableError("SerpApi key is not configured.")
        response = self.client.youtube_video(video_id=payload.video_id, hl=payload.hl)
        info = response.get("video_details", {}) or response.get("video", {}) or {}
        return YouTubeVideoOutput(
            title=str(info.get("title") or "").strip(),
            channel_name=str(info.get("channel") or info.get("channel_name") or "").strip(),
            description=str(info.get("description") or "").strip(),
            views=str(info.get("views") or info.get("view_count") or "").strip(),
            publish_date=str(info.get("published") or info.get("date") or "").strip(),
            likes=str(info.get("likes") or "").strip(),
            link=f"https://www.youtube.com/watch?v={payload.video_id}",
            raw_payload=response,
            usage=ToolUsage(),
        )


class AviationstackFlightScheduleTool:
    name = "flight_schedule_lookup"
    metadata = ToolMetadata(
        name="flight_schedule_lookup",
        description="Looks up candidate airports and scheduled flights through Aviationstack for flight enrichment.",
        allowed_agents=("destination_research_agent",),
        provider_name="aviationstack",
        provider_endpoint="airports/flights",
        auth_method=ToolAuthMethod.API_KEY,
        timeout_seconds=20,
        retry_policy="retry_once",
        rate_limit_per_minute=20,
        side_effect_level=ToolSideEffectLevel.EXTERNAL_READ,
        input_model=FlightScheduleLookupInput,
        output_model=FlightScheduleLookupOutput,
    )

    def __init__(self, client: AviationstackClient | None) -> None:
        self.client = client

    def is_available(self) -> bool:
        return self.client is not None

    def execute(self, payload: FlightScheduleLookupInput) -> FlightScheduleLookupOutput:
        if self.client is None:
            raise ToolUnavailableError("Aviationstack API key is not configured.")
        origin_airports = resolve_known_airports(payload.origin_city)
        destination_airports = resolve_known_airports(payload.destination_city)

        flights: list[FlightScheduleOption] = []
        raw_flights_payload: dict[str, Any] = {}
        if origin_airports and destination_airports:
            raw_flights_payload = self.client.flights(
                flight_date=payload.flight_date,
                dep_iata=origin_airports[0],
                arr_iata=destination_airports[0],
            )
            for item in raw_flights_payload.get("data", [])[:5]:
                flight = item.get("flight", {}) or {}
                departure = item.get("departure", {}) or {}
                arrival = item.get("arrival", {}) or {}
                airline = item.get("airline", {}) or {}
                flights.append(
                    FlightScheduleOption(
                        airline=str(airline.get("name") or "").strip(),
                        flight_number=str(flight.get("number") or "").strip(),
                        departure_airport=str(departure.get("airport") or "").strip(),
                        arrival_airport=str(arrival.get("airport") or "").strip(),
                        scheduled_departure=str(departure.get("scheduled") or "").strip(),
                        scheduled_arrival=str(arrival.get("scheduled") or "").strip(),
                        flight_status=str(item.get("flight_status") or "").strip(),
                    )
                )
        if flights:
            summary = "; ".join(
                f"{item.airline or 'Airline n/a'} {item.flight_number or ''} | {item.flight_status or 'status n/a'}"
                for item in flights[:3]
            )
        elif origin_airports and destination_airports:
            summary = (
                "No scheduled flight matches returned for "
                f"{origin_airports[0]} to {destination_airports[0]} on {payload.flight_date}."
            )
        else:
            summary = (
                "Aviationstack schedule enrichment is running in limited mode and could not resolve "
                f"airport codes for '{payload.origin_city}' or '{payload.destination_city}'."
            )
        return FlightScheduleLookupOutput(
            summary=summary,
            origin_airports=origin_airports[:5],
            destination_airports=destination_airports[:5],
            flights=flights,
            raw_payload={
                "origin_resolution": {"query": payload.origin_city, "codes": origin_airports[:5]},
                "destination_resolution": {"query": payload.destination_city, "codes": destination_airports[:5]},
                "flights": raw_flights_payload,
            },
            usage=ToolUsage(),
        )
