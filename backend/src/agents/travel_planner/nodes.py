from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol
from urllib.parse import quote_plus

from pydantic import ValidationError

from src.agents.travel_planner.governance import evaluate_governance
from src.agents.travel_planner.research_clients import ResearchClientError, days_until
from src.agents.travel_planner.research_prompts import (
    BUDGET_OPTIMIZATION_DEVELOPER_PROMPT,
    DESTINATION_RESEARCH_DEVELOPER_PROMPT,
    FOOD_RECOMMENDATION_DEVELOPER_PROMPT,
    ITINERARY_PLANNING_DEVELOPER_PROMPT,
    LOCAL_TRANSPORT_DEVELOPER_PROMPT,
    REVIEW_AND_CONSISTENCY_DEVELOPER_PROMPT,
    SOLO_WOMEN_SAFETY_DEVELOPER_PROMPT,
    STAY_RECOMMENDATION_DEVELOPER_PROMPT,
    build_budget_optimization_prompt,
    build_destination_research_prompt,
    build_food_recommendation_prompt,
    build_itinerary_planning_prompt,
    build_local_transport_prompt,
    build_review_and_consistency_prompt,
    build_solo_women_safety_prompt,
    build_stay_recommendation_prompt,
)
from src.agents.travel_planner.schemas import (
    BudgetAssessment,
    DestinationResearchReport,
    FoodRecommendation,
    FoodRecommendationPlan,
    ItineraryDayPlan,
    ItineraryPlan,
    ItinerarySuggestion,
    LocalTransportPlan,
    ResearchSource,
    ReviewAssessment,
    SoloWomenSafetyAssessment,
    StayRecommendation,
    StayRecommendationPlan,
    TransportLegRecommendation,
    TripStatus,
    WeatherSnapshot,
)
from src.agents.travel_planner.state import PlannerContext
from src.agents.travel_planner.tooling.base import JsonCompletionInput
from src.agents.travel_planner.tooling.airports import resolve_known_airports
from src.agents.travel_planner.tooling.provider_tools import (
    GoogleFlightsInput,
    GoogleHotelsInput,
    TripadvisorSearchInput,
    WeatherLookupInput,
    WebSearchInput,
    WebSearchOutput,
    build_tool_executor,
)
from src.agents.travel_planner.tools import parse_iso_date
from src.domain.trips.policies import ClarificationPolicy
from src.domain.trips.services import TripResearchSignalService


class PlannerAgent(Protocol):
    name: str

    def run(self, context: PlannerContext) -> PlannerContext: ...


def _build_google_search_url(query: str) -> str:
    cleaned = " ".join(query.split()).strip()
    if not cleaned:
        return ""
    return f"https://www.google.com/search?q={quote_plus(cleaned)}"


def _build_google_maps_url(query: str) -> str:
    cleaned = " ".join(query.split()).strip()
    if not cleaned:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(cleaned)}"


def _build_youtube_search_url(query: str) -> str:
    cleaned = " ".join(query.split()).strip()
    if not cleaned:
        return ""
    return f"https://www.youtube.com/results?search_query={quote_plus(cleaned)}"


def _build_booking_search_url(query: str) -> str:
    cleaned = " ".join(query.split()).strip()
    if not cleaned:
        return ""
    return f"https://www.booking.com/searchresults.html?ss={quote_plus(cleaned)}"


@dataclass
class ClarificationValidator:
    name: str = "clarification_validator"
    policy: ClarificationPolicy = ClarificationPolicy()

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        context.clarification_questions = self.policy.build_questions(context.request)
        context.status = self.policy.status_for(context.clarification_questions)
        return context


@dataclass
class ResearchSignalAgent:
    name: str = "research_signal_agent"
    signal_service: TripResearchSignalService = TripResearchSignalService()

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        context.research_signals = self.signal_service.build(context.request)
        return context


@dataclass
class DestinationResearchAgent:
    name: str = "destination_research_agent"
    max_queries: int = 4

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        executor = build_tool_executor(context, self.name)
        request = context.request

        weather_snapshot = self._gather_weather(
            request.destination,
            request.start_date,
            executor,
        )
        tavily_bundle = self._gather_web_research(context, executor)
        flights_bundle = self._gather_flight_inventory(context, executor)
        research_report = self._synthesize_report(
            context,
            weather_snapshot,
            tavily_bundle,
            flights_bundle,
            executor,
        )

        context.destination_research = research_report
        context.status = TripStatus.RESEARCH_COMPLETE
        return context

    def _gather_weather(
        self,
        destination: str,
        start_date: str,
        executor,
    ) -> WeatherSnapshot | None:
        if not executor.registry.is_available("weather_lookup"):
            return None

        try:
            current_payload = executor.execute(
                "weather_lookup",
                WeatherLookupInput(location=destination),
            ).payload
            target_date = parse_iso_date(start_date)
            location_name = current_payload.get("location", {}).get("name", destination)
            current = current_payload.get("current", {})
            current_summary = current.get("condition", {}).get("text", "Current conditions unavailable")
            current_temp_c = current.get("temp_c")

            if target_date is None:
                return WeatherSnapshot(
                    location=location_name,
                    summary=f"Current conditions: {current_summary}. Trip dates could not be parsed for a forecast window.",
                    trip_window="invalid_dates",
                    current_temp_c=current_temp_c,
                )

            days_out = days_until(target_date.date(), date.today())
            if 0 <= days_out <= 13:
                forecast_payload = executor.execute(
                    "weather_lookup",
                    WeatherLookupInput(location=destination, forecast_days=days_out + 1),
                ).payload
                forecast_days = forecast_payload.get("forecast", {}).get("forecastday", [])
                day_payload = forecast_days[-1].get("day", {}) if forecast_days else {}
                chance_of_rain = day_payload.get("daily_chance_of_rain")
                avg_temp = day_payload.get("avgtemp_c")
                max_temp = day_payload.get("maxtemp_c")
                min_temp = day_payload.get("mintemp_c")
                condition = day_payload.get("condition", {}).get("text", current_summary)
                summary = (
                    f"Forecast for trip start is {condition.lower()} with average {avg_temp}C, "
                    f"high {max_temp}C, low {min_temp}C."
                )
                return WeatherSnapshot(
                    location=location_name,
                    summary=summary,
                    trip_window="forecast",
                    current_temp_c=current_temp_c,
                    forecast_avg_temp_c=avg_temp,
                    forecast_max_temp_c=max_temp,
                    forecast_min_temp_c=min_temp,
                    chance_of_rain=int(chance_of_rain) if chance_of_rain is not None else None,
                )

            return WeatherSnapshot(
                location=location_name,
                summary=(
                    f"Current conditions are {current_summary.lower()} at {current_temp_c}C. "
                    "Trip dates are beyond the near-term forecast window, so this is only a directional weather signal."
                ),
                trip_window="current_only",
                current_temp_c=current_temp_c,
            )
        except ResearchClientError as exc:
            return WeatherSnapshot(
                location=destination,
                summary=f"Weather research failed: {exc}",
                trip_window="unavailable",
            )

    def _gather_web_research(self, context: PlannerContext, executor) -> dict[str, object]:
        request = context.request
        if not executor.registry.is_available("web_search"):
            return {"summary": "Tavily API key is not configured.", "sources": []}

        queries = [
            f"{request.destination} best areas to stay for {request.trip_purpose.value} travel",
            f"{request.destination} top things to do for {', '.join(request.interests[:3]) or request.trip_purpose.value}",
            f"{request.destination} hotel prices and local transport costs for travelers",
            f"{request.destination} travel tips safety logistics and airport access",
        ][: self.max_queries]

        try:
            result = executor.execute("web_search", WebSearchInput(queries=queries))
        except ResearchClientError as exc:
            return {"summary": f"Web research failed: {exc}", "sources": []}

        return {"summary": result.summary, "sources": result.sources}

    def _gather_flight_inventory(self, context: PlannerContext, executor) -> dict[str, object]:
        if not executor.registry.is_available("google_flights_search"):
            return {"summary": "SerpApi Google Flights enrichment is not configured."}

        request = context.request
        origin_airports = resolve_known_airports(request.origin_city)
        destination_airports = resolve_known_airports(request.destination)

        if not origin_airports or not destination_airports:
            return {
                "summary": (
                    "Structured flight inventory lookup was skipped because airport codes could not be resolved "
                    f"for origin '{request.origin_city}' or destination '{request.destination}'."
                ),
                "origin_airports": origin_airports,
                "destination_airports": destination_airports,
            }

        try:
            result = executor.execute(
                "google_flights_search",
                GoogleFlightsInput(
                    departure_id=origin_airports[0],
                    arrival_id=destination_airports[0],
                    outbound_date=request.start_date,
                    return_date=request.end_date,
                    adults=request.traveler_count,
                    currency="INR",
                    hl="en",
                    gl="in",
                ),
            )
        except ResearchClientError as exc:
            return {
                "summary": f"Structured flight inventory lookup failed: {exc}",
                "origin_airports": origin_airports,
                "destination_airports": destination_airports,
            }
        return {
            "summary": (
                f"Resolved origin airport: {origin_airports[0]}. "
                f"Resolved destination airport: {destination_airports[0]}. "
                f"Google Flights context: {result.summary}"
            ),
            "origin_airports": origin_airports,
            "destination_airports": destination_airports,
            "best_flights": [item.model_dump() for item in result.best_flights],
        }

    def _synthesize_report(
        self,
        context: PlannerContext,
        weather_snapshot: WeatherSnapshot | None,
        tavily_bundle: dict[str, object],
        flights_bundle: dict[str, object],
        executor,
    ) -> DestinationResearchReport:
        request = context.request
        sources = tavily_bundle.get("sources", [])
        if not isinstance(sources, list):
            sources = []

        if not executor.registry.is_available("json_completion"):
            return self._fallback_report(context, weather_snapshot, sources, "OpenAI API key is not configured.")

        prompt = build_destination_research_prompt(
            request=request,
            research_signals=context.research_signals,
            weather_summary=weather_snapshot.summary if weather_snapshot else "No weather data available.",
            flight_context_summary=str(flights_bundle.get("summary", "No structured flight inventory available.")),
            web_research_summary=self._combine_destination_research_summaries(
                str(tavily_bundle.get("summary", "No web research available.")),
                str(flights_bundle.get("summary", "No structured flight inventory available.")),
            ),
        )

        try:
            payload = executor.execute(
                "json_completion",
                JsonCompletionInput(
                    developer_prompt=DESTINATION_RESEARCH_DEVELOPER_PROMPT,
                    user_prompt=prompt,
                ),
            ).payload
        except (ResearchClientError, ValidationError) as exc:
            return self._fallback_report(context, weather_snapshot, sources, str(exc))

        return DestinationResearchReport(
            destination=request.destination,
            summary=str(payload.get("summary") or "Destination research completed with limited synthesis."),
            weather=weather_snapshot,
            budget_per_day_estimate=context.research_signals.get("budget_per_day"),
            interest_fit=self._coerce_list(payload.get("interest_fit")),
            recommended_areas=self._coerce_list(payload.get("recommended_areas")),
            local_transport_notes=self._coerce_list(payload.get("local_transport_notes")),
            top_highlights=self._coerce_list(payload.get("top_highlights")),
            top_risks=self._coerce_list(payload.get("top_risks")),
            planning_tips=self._coerce_list(payload.get("planning_tips")),
            hotel_price_signal=self._coerce_optional_string(payload.get("hotel_price_signal")),
            flight_price_signal=self._coerce_optional_string(payload.get("flight_price_signal")),
            flight_context_summary=str(flights_bundle.get("summary", "No structured flight inventory available.")),
            assumptions=self._coerce_list(payload.get("assumptions")),
            confidence=self._coerce_confidence(payload.get("confidence")),
            sources=sources[:8],
        )

    def _combine_destination_research_summaries(self, web_summary: str, flights_summary: str) -> str:
        return (
            f"General web research:\n{web_summary}\n\n"
            f"Structured flight inventory:\n{flights_summary}"
        ).strip()

    def _fallback_report(
        self,
        context: PlannerContext,
        weather_snapshot: WeatherSnapshot | None,
        sources: list[ResearchSource],
        reason: str,
    ) -> DestinationResearchReport:
        request = context.request
        budget_per_day = context.research_signals.get("budget_per_day")
        return DestinationResearchReport(
            destination=request.destination,
            summary=(
                f"Initial research for {request.destination} was assembled, but the synthesis step stayed partial. "
                f"The agent fallback was used because: {reason}"
            ),
            weather=weather_snapshot,
            budget_per_day_estimate=float(budget_per_day) if isinstance(budget_per_day, (int, float)) else None,
            interest_fit=request.interests[:3],
            recommended_areas=[],
            local_transport_notes=[request.transport_preference or "Transport preference not provided."],
            top_highlights=[
                f"Trip purpose: {request.trip_purpose.value}",
                f"Budget tier: {request.budget_tier.value}",
            ],
            top_risks=["Research confidence is limited until external synthesis succeeds."],
            planning_tips=["Review source links before turning this research into a day-by-day itinerary."],
            hotel_price_signal="Estimated from public web research only.",
            flight_price_signal="Estimated from public web research only.",
            flight_context_summary="Structured flight enrichment was not available during this run.",
            assumptions=["Trip inputs were treated as final clarified data."],
            confidence=0.25,
            sources=sources[:8],
        )

    def _coerce_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _coerce_optional_string(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))


@dataclass
class ItineraryPlanningAgent:
    name: str = "itinerary_planning_agent"

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        executor = build_tool_executor(context, self.name)

        if context.destination_research is None:
            context.itinerary_plan = self._fallback_plan(
                context,
                "Destination research is required before itinerary planning.",
            )
            context.status = TripStatus.ITINERARY_READY
            return context

        if not executor.registry.is_available("json_completion"):
            context.itinerary_plan = self._fallback_plan(context, "OpenAI API key is not configured.")
            context.status = TripStatus.ITINERARY_READY
            return context

        prompt = build_itinerary_planning_prompt(
            request=context.request,
            research_signals=context.research_signals,
            destination_research_summary=context.destination_research.summary,
            destination_research_areas=context.destination_research.recommended_areas,
            destination_research_highlights=context.destination_research.top_highlights,
            destination_transport_notes=context.destination_research.local_transport_notes,
            destination_risks=context.destination_research.top_risks,
        )

        try:
            payload = executor.execute(
                "json_completion",
                JsonCompletionInput(
                    developer_prompt=ITINERARY_PLANNING_DEVELOPER_PROMPT,
                    user_prompt=prompt,
                ),
            ).payload
            itinerary_plan = self._coerce_itinerary_plan(context, payload, executor)
        except (ResearchClientError, ValidationError) as exc:
            itinerary_plan = self._fallback_plan(context, str(exc), executor)

        context.itinerary_plan = itinerary_plan
        context.status = TripStatus.ITINERARY_READY
        return context

    def _coerce_itinerary_plan(self, context: PlannerContext, payload: dict[str, object], executor) -> ItineraryPlan:
        request = context.request
        expected_dates = self._trip_dates(request.start_date, request.end_date)
        raw_days = payload.get("days")
        days: list[ItineraryDayPlan] = []

        if isinstance(raw_days, list):
            for index, item in enumerate(raw_days[: len(expected_dates)]):
                if not isinstance(item, dict):
                    continue
                day_date = str(item.get("date") or expected_dates[index]).strip()
                if day_date not in expected_dates:
                    day_date = expected_dates[index]
                area = str(item.get("area") or self._default_area(context)).strip()
                recommended_restaurant = str(
                    item.get("recommended_restaurant") or self._default_restaurant(context, index + 1)
                ).strip()
                photo_spot = str(item.get("photo_spot") or self._default_photo_spot(context)).strip()
                days.append(
                    ItineraryDayPlan(
                        day_number=index + 1,
                        date=day_date,
                        theme=str(item.get("theme") or f"Day {index + 1} exploration").strip(),
                        morning=str(item.get("morning") or "Flexible morning").strip(),
                        morning_suggestions=self._coerce_suggestions(
                            item.get("morning_suggestions"),
                            context=context,
                            period="morning",
                            area=area,
                            day_number=index + 1,
                        ),
                        afternoon=str(item.get("afternoon") or "Flexible afternoon").strip(),
                        afternoon_suggestions=self._coerce_suggestions(
                            item.get("afternoon_suggestions"),
                            context=context,
                            period="afternoon",
                            area=area,
                            day_number=index + 1,
                        ),
                        evening=str(item.get("evening") or "Flexible evening").strip(),
                        evening_suggestions=self._coerce_suggestions(
                            item.get("evening_suggestions"),
                            context=context,
                            period="evening",
                            area=area,
                            day_number=index + 1,
                        ),
                        area=area,
                        transport_note=str(item.get("transport_note") or self._default_transport_note(context)).strip(),
                        recommended_restaurant=recommended_restaurant,
                        restaurant_maps_url=self._coerce_url(item.get("restaurant_maps_url"))
                        or self._build_restaurant_maps_url(context, recommended_restaurant, area),
                        restaurant_website_url=self._coerce_url(item.get("restaurant_website_url")),
                        restaurant_review_video_urls=self._coerce_url_list(item.get("restaurant_review_video_urls"))[:3]
                        or self._default_restaurant_review_video_urls(context, recommended_restaurant),
                        best_restaurant_short_url=self._coerce_url(item.get("best_restaurant_short_url")),
                        signature_dishes=self._coerce_list(item.get("signature_dishes"))[:3]
                        or self._default_signature_dishes(context),
                        photo_spot=photo_spot,
                        photo_timing=str(item.get("photo_timing") or self._default_photo_timing(index + 1)).strip(),
                        photo_maps_url=self._coerce_url(item.get("photo_maps_url"))
                        or self._build_photo_maps_url(context, photo_spot, area),
                        photo_blog_urls=self._coerce_url_list(item.get("photo_blog_urls"))[:3]
                        or self._default_photo_blog_urls(context, photo_spot),
                        photo_vlog_urls=self._coerce_url_list(item.get("photo_vlog_urls"))[:3]
                        or self._default_photo_vlog_urls(context, photo_spot),
                        best_photo_short_url=self._coerce_url(item.get("best_photo_short_url")),
                        pace_level=str(item.get("pace_level") or context.request.pace).strip(),
                        estimated_daily_cost=str(
                            item.get("estimated_daily_cost") or self._default_daily_cost(context)
                        ).strip(),
                        reasoning=str(
                            item.get("reasoning") or "Built from destination research and trip preferences."
                        ).strip(),
                        warnings=self._coerce_list(item.get("warnings")),
                    )
                )

        while len(days) < len(expected_dates):
            day_number = len(days) + 1
            days.append(
                ItineraryDayPlan(
                    day_number=day_number,
                    date=expected_dates[day_number - 1],
                    theme=f"Day {day_number} flexible exploration",
                    morning="Light local exploration near the base area.",
                    morning_suggestions=self._default_period_suggestions(context, "morning", self._default_area(context), day_number),
                    afternoon="Priority sightseeing aligned with the trip interests.",
                    afternoon_suggestions=self._default_period_suggestions(context, "afternoon", self._default_area(context), day_number),
                    evening="Relaxed dinner and neighborhood walk.",
                    evening_suggestions=self._default_period_suggestions(context, "evening", self._default_area(context), day_number),
                    area=self._default_area(context),
                    transport_note=self._default_transport_note(context),
                    recommended_restaurant=self._default_restaurant(context, day_number),
                    restaurant_maps_url=self._build_restaurant_maps_url(
                        context,
                        self._default_restaurant(context, day_number),
                        self._default_area(context),
                    ),
                    restaurant_website_url="",
                    restaurant_review_video_urls=self._default_restaurant_review_video_urls(
                        context,
                        self._default_restaurant(context, day_number),
                    ),
                    best_restaurant_short_url="",
                    signature_dishes=self._default_signature_dishes(context),
                    photo_spot=self._default_photo_spot(context),
                    photo_timing=self._default_photo_timing(day_number),
                    photo_maps_url=self._build_photo_maps_url(
                        context,
                        self._default_photo_spot(context),
                        self._default_area(context),
                    ),
                    photo_blog_urls=self._default_photo_blog_urls(context, self._default_photo_spot(context)),
                    photo_vlog_urls=self._default_photo_vlog_urls(context, self._default_photo_spot(context)),
                    best_photo_short_url="",
                    pace_level=context.request.pace,
                    estimated_daily_cost=self._default_daily_cost(context),
                    reasoning="Added as a fallback to preserve a complete trip structure.",
                    warnings=["This day was filled by fallback logic because the model output was incomplete."],
                )
            )

        plan = ItineraryPlan(
            destination=request.destination,
            summary=str(
                payload.get("summary") or f"{request.destination} itinerary drafted for {len(days)} days."
            ).strip(),
            days=days,
            budget_fit_note=str(
                payload.get("budget_fit_note")
                or f"Daily planning is aligned to an estimated budget of {self._default_daily_cost(context)}."
            ).strip(),
            assumptions=self._coerce_list(payload.get("assumptions")),
            confidence=self._coerce_confidence(payload.get("confidence")),
        )
        return self._enrich_best_short_urls(context, executor, plan)

    def _fallback_plan(self, context: PlannerContext, reason: str, executor) -> ItineraryPlan:
        request = context.request
        dates = self._trip_dates(request.start_date, request.end_date)
        days: list[ItineraryDayPlan] = []
        for index, day_date in enumerate(dates, start=1):
            is_first = index == 1
            is_last = index == len(dates)
            area = self._default_area(context)
            restaurant = self._default_restaurant(context, index)
            photo_spot = self._default_photo_spot(context)
            days.append(
                ItineraryDayPlan(
                    day_number=index,
                    date=day_date,
                    theme="Arrival and orientation"
                    if is_first
                    else "Departure and wrap-up"
                    if is_last
                    else "Core exploration day",
                    morning="Arrival logistics and a gentle start."
                    if is_first
                    else "Primary sightseeing block near the main activity area.",
                    morning_suggestions=self._default_period_suggestions(context, "morning", area, index),
                    afternoon="Neighborhood exploration and a flexible lunch window.",
                    afternoon_suggestions=self._default_period_suggestions(context, "afternoon", area, index),
                    evening="Relaxed dinner and recovery time."
                    if is_last
                    else "Dinner and low-intensity evening activity.",
                    evening_suggestions=self._default_period_suggestions(context, "evening", area, index),
                    area=area,
                    transport_note=self._default_transport_note(context),
                    recommended_restaurant=restaurant,
                    restaurant_maps_url=self._build_restaurant_maps_url(context, restaurant, area),
                    restaurant_website_url="",
                    restaurant_review_video_urls=self._default_restaurant_review_video_urls(context, restaurant),
                    best_restaurant_short_url="",
                    signature_dishes=self._default_signature_dishes(context),
                    photo_spot=photo_spot,
                    photo_timing=self._default_photo_timing(index),
                    photo_maps_url=self._build_photo_maps_url(context, photo_spot, area),
                    photo_blog_urls=self._default_photo_blog_urls(context, photo_spot),
                    photo_vlog_urls=self._default_photo_vlog_urls(context, photo_spot),
                    best_photo_short_url="",
                    pace_level=request.pace,
                    estimated_daily_cost=self._default_daily_cost(context),
                    reasoning="Fallback itinerary generated from destination research and core trip inputs.",
                    warnings=[f"Fallback itinerary used because: {reason}"],
                )
            )

        plan = ItineraryPlan(
            destination=request.destination,
            summary=f"A fallback itinerary was created for {request.destination} because the primary synthesis step was unavailable.",
            days=days,
            budget_fit_note=f"Use {self._default_daily_cost(context)} as an initial daily planning target.",
            assumptions=["Arrival and departure timing were not explicitly provided."],
            confidence=0.25,
        )
        return self._enrich_best_short_urls(context, executor, plan)

    def _enrich_best_short_urls(self, context: PlannerContext, executor, plan: ItineraryPlan) -> ItineraryPlan:
        self._enrich_period_suggestions(context, executor, plan)

        if not executor.registry.is_available("web_search"):
            for day in plan.days:
                day.best_restaurant_short_url = (
                    day.best_restaurant_short_url
                    or (day.restaurant_review_video_urls[0] if day.restaurant_review_video_urls else "")
                )
                day.best_photo_short_url = (
                    day.best_photo_short_url
                    or (day.photo_vlog_urls[0] if day.photo_vlog_urls else "")
                )
            return plan

        for day in plan.days:
            if not day.best_restaurant_short_url:
                ranked_restaurant_urls = self._rank_youtube_urls_for_subject(
                    context=context,
                    executor=executor,
                    subject=day.recommended_restaurant,
                    fallback_urls=day.restaurant_review_video_urls,
                    query_suffix="food review shorts",
                )
                if ranked_restaurant_urls:
                    day.restaurant_review_video_urls = ranked_restaurant_urls[:3]
                    day.best_restaurant_short_url = ranked_restaurant_urls[0]
            if not day.best_photo_short_url:
                ranked_photo_urls = self._rank_youtube_urls_for_subject(
                    context=context,
                    executor=executor,
                    subject=day.photo_spot,
                    fallback_urls=day.photo_vlog_urls,
                    query_suffix="photo spot photography shorts",
                )
                if ranked_photo_urls:
                    day.photo_vlog_urls = ranked_photo_urls[:3]
                    day.best_photo_short_url = ranked_photo_urls[0]
        return plan

    def _enrich_period_suggestions(self, context: PlannerContext, executor, plan: ItineraryPlan) -> None:
        for day in plan.days:
            if not day.morning_suggestions:
                day.morning_suggestions = self._search_backed_period_suggestions(
                    context=context,
                    executor=executor,
                    period="morning",
                    period_text=day.morning,
                    area=day.area,
                    fallback=self._default_period_suggestions(context, "morning", day.area, day.day_number),
                )
            if not day.afternoon_suggestions:
                day.afternoon_suggestions = self._search_backed_period_suggestions(
                    context=context,
                    executor=executor,
                    period="afternoon",
                    period_text=day.afternoon,
                    area=day.area,
                    fallback=self._default_period_suggestions(context, "afternoon", day.area, day.day_number),
                )
            if not day.evening_suggestions:
                day.evening_suggestions = self._search_backed_period_suggestions(
                    context=context,
                    executor=executor,
                    period="evening",
                    period_text=day.evening,
                    area=day.area,
                    fallback=self._default_period_suggestions(context, "evening", day.area, day.day_number),
                )

    def _search_backed_period_suggestions(
        self,
        *,
        context: PlannerContext,
        executor,
        period: str,
        period_text: str,
        area: str,
        fallback: list[ItinerarySuggestion],
    ) -> list[ItinerarySuggestion]:
        if not executor.registry.is_available("web_search"):
            return fallback

        query = (
            f"{context.request.destination} {area} {period} "
            f"{period_text} activities official site things to do"
        )
        try:
            result = executor.execute(
                "web_search",
                WebSearchInput(
                    queries=[query],
                    max_results=4,
                    results_per_query=4,
                ),
            )
        except ResearchClientError:
            return fallback

        suggestions: list[ItinerarySuggestion] = []
        for source in result.sources[:3]:
            title = " ".join(str(source.title).split()).strip()
            if not title:
                continue
            suggestions.append(
                ItinerarySuggestion(
                    title=title,
                    website_url=source.url.strip(),
                    maps_url=_build_google_maps_url(f"{title} {area} {context.request.destination}"),
                )
            )

        return suggestions or fallback

    def _rank_youtube_urls_for_subject(
        self,
        *,
        context: PlannerContext,
        executor,
        subject: str,
        fallback_urls: list[str],
        query_suffix: str,
    ) -> list[str]:
        direct_candidates = [url for url in fallback_urls if self._is_direct_youtube_url(url)]
        ranked_existing = self._rank_direct_youtube_urls(subject, context.request.destination, direct_candidates)
        if ranked_existing:
            return ranked_existing

        if not subject.strip():
            return fallback_urls[:3]

        try:
            result = executor.execute(
                "web_search",
                WebSearchInput(
                    queries=[f"site:youtube.com {subject} {context.request.destination} {query_suffix}"],
                    max_results=4,
                    results_per_query=4,
                ),
            )
        except ResearchClientError:
            return fallback_urls[:3] if fallback_urls else [
                _build_youtube_search_url(f"{subject} {context.request.destination} {query_suffix}")
            ]

        ranked_from_sources = self._rank_youtube_source_urls(
            subject=subject,
            destination=context.request.destination,
            output=result,
        )
        if ranked_from_sources:
            return ranked_from_sources[:3]

        return fallback_urls[:3] if fallback_urls else [
            _build_youtube_search_url(f"{subject} {context.request.destination} {query_suffix}")
        ]

    def _rank_youtube_source_urls(self, *, subject: str, destination: str, output: WebSearchOutput) -> list[str]:
        scored: list[tuple[int, str]] = []
        subject_tokens = self._tokenize(subject)
        destination_tokens = self._tokenize(destination)
        for source in output.sources:
            url = source.url.strip()
            if not self._is_direct_youtube_url(url):
                continue
            haystack = f"{source.title} {source.snippet} {url}".lower()
            score = 0
            if "shorts" in url:
                score += 8
            if "youtube.com/watch" in url or "youtu.be/" in url:
                score += 4
            score += sum(3 for token in subject_tokens if token and token in haystack)
            score += sum(2 for token in destination_tokens if token and token in haystack)
            for keyword in ("sunset", "golden hour", "photo", "photography", "review", "food", "cafe", "restaurant"):
                if keyword in haystack:
                    score += 1
            scored.append((score, url))
        scored.sort(key=lambda item: item[0], reverse=True)
        ranked_urls: list[str] = []
        for _, url in scored:
            if url not in ranked_urls:
                ranked_urls.append(url)
        return ranked_urls[:3]

    def _rank_direct_youtube_urls(self, subject: str, destination: str, urls: list[str]) -> list[str]:
        if not urls:
            return []
        scored: list[tuple[int, str]] = []
        haystack_tokens = self._tokenize(subject) + self._tokenize(destination)
        for url in urls:
            lowered = url.lower()
            score = 0
            if "shorts" in lowered:
                score += 8
            if "watch?v=" in lowered or "youtu.be/" in lowered:
                score += 4
            score += sum(1 for token in haystack_tokens if token and token in lowered)
            scored.append((score, url))
        scored.sort(key=lambda item: item[0], reverse=True)
        ranked_urls: list[str] = []
        for _, url in scored:
            if url not in ranked_urls:
                ranked_urls.append(url)
        return ranked_urls[:3]

    def _is_direct_youtube_url(self, url: str) -> bool:
        lowered = url.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            return False
        return "youtube.com/shorts/" in lowered or "youtube.com/watch" in lowered or "youtu.be/" in lowered

    def _tokenize(self, value: str) -> list[str]:
        return [token for token in value.lower().replace(",", " ").split() if len(token) > 2]

    def _trip_dates(self, start_date: str, end_date: str) -> list[str]:
        start = parse_iso_date(start_date)
        end = parse_iso_date(end_date)
        if start is None or end is None or end < start:
            return [start_date]

        dates: list[str] = []
        cursor = start.date()
        while cursor <= end.date():
            dates.append(cursor.isoformat())
            cursor += timedelta(days=1)
        return dates

    def _default_area(self, context: PlannerContext) -> str:
        if context.destination_research and context.destination_research.recommended_areas:
            return context.destination_research.recommended_areas[0]
        return context.request.destination

    def _default_transport_note(self, context: PlannerContext) -> str:
        if context.destination_research and context.destination_research.local_transport_notes:
            return context.destination_research.local_transport_notes[0]
        return context.request.transport_preference or "Use practical local transport based on the day plan."

    def _default_restaurant(self, context: PlannerContext, day_number: int) -> str:
        if context.food_recommendation_plan:
            for recommendation in context.food_recommendation_plan.recommendations:
                if recommendation.day_number == day_number:
                    return recommendation.venue_name
        return f"Popular local restaurant in {self._default_area(context)}"

    def _default_signature_dishes(self, context: PlannerContext) -> list[str]:
        interests = {interest.lower() for interest in context.request.interests}
        if "food" in interests:
            return ["Regional signature dish", "Popular house specialty", "Local dessert"]
        return ["Regional signature dish", "Seasonal specialty"]

    def _default_restaurant_review_video_urls(self, context: PlannerContext, restaurant: str) -> list[str]:
        return [
            _build_youtube_search_url(
                f"{restaurant} {context.request.destination} food review shorts"
            )
        ]

    def _default_photo_spot(self, context: PlannerContext) -> str:
        if context.destination_research and context.destination_research.top_highlights:
            return context.destination_research.top_highlights[0]
        return f"Scenic spot in {self._default_area(context)}"

    def _default_photo_timing(self, day_number: int) -> str:
        return "Golden hour near sunset" if day_number % 2 == 0 else "Early morning or sunrise"

    def _build_restaurant_maps_url(self, context: PlannerContext, restaurant: str, area: str) -> str:
        return _build_google_maps_url(f"{restaurant} {area} {context.request.destination}")

    def _build_photo_maps_url(self, context: PlannerContext, photo_spot: str, area: str) -> str:
        return _build_google_maps_url(f"{photo_spot or area} {context.request.destination}")

    def _default_photo_blog_urls(self, context: PlannerContext, photo_spot: str) -> list[str]:
        return [
            _build_google_search_url(
                f"{photo_spot} {context.request.destination} best photo spot travel blog"
            )
        ]

    def _default_photo_vlog_urls(self, context: PlannerContext, photo_spot: str) -> list[str]:
        return [
            _build_youtube_search_url(
                f"{photo_spot} {context.request.destination} travel vlog photography"
            )
        ]

    def _default_daily_cost(self, context: PlannerContext) -> str:
        budget = context.research_signals.get("budget_per_day")
        if isinstance(budget, (int, float)):
            return f"Approximately {round(float(budget), 2)} total per day"
        return "Estimated from budget tier and destination research"

    def _coerce_suggestions(
        self,
        value: object,
        *,
        context: PlannerContext,
        period: str,
        area: str,
        day_number: int,
    ) -> list[ItinerarySuggestion]:
        suggestions: list[ItinerarySuggestion] = []
        if isinstance(value, list):
            for item in value[:3]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                suggestions.append(
                    ItinerarySuggestion(
                        title=title,
                        website_url=self._coerce_url(item.get("website_url")),
                        maps_url=self._coerce_url(item.get("maps_url"))
                        or _build_google_maps_url(f"{title} {area} {context.request.destination}"),
                    )
                )
        if suggestions:
            return suggestions
        return self._default_period_suggestions(context, period, area, day_number)

    def _default_period_suggestions(
        self,
        context: PlannerContext,
        period: str,
        area: str,
        day_number: int,
    ) -> list[ItinerarySuggestion]:
        base = [
            f"{area} {period} highlight",
            f"{context.request.destination} {period} local pick",
            f"Day {day_number} {period} practical stop",
        ]
        suggestions: list[ItinerarySuggestion] = []
        for title in base[:3]:
            suggestions.append(
                ItinerarySuggestion(
                    title=title,
                    website_url=_build_google_search_url(f"{title} official website"),
                    maps_url=_build_google_maps_url(f"{title} {area} {context.request.destination}"),
                )
            )
        return suggestions

    def _coerce_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _coerce_url(self, value: object) -> str:
        if not isinstance(value, str):
            return ""
        cleaned = value.strip()
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        return ""

    def _coerce_url_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        urls: list[str] = []
        for item in value:
            url = self._coerce_url(item)
            if url and url not in urls:
                urls.append(url)
        return urls

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))


@dataclass
class StayRecommendationAgent:
    name: str = "stay_recommendation_agent"

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        executor = build_tool_executor(context, self.name)

        if context.itinerary_plan is None:
            context.stay_recommendation_plan = self._fallback_plan(
                context,
                "Itinerary plan is required before stay recommendations.",
            )
            return context

        tavily_bundle = self._gather_web_research(context, executor)
        hotel_bundle = self._gather_hotel_inventory(context, executor)
        tripadvisor_bundle = self._gather_tripadvisor_context(context, executor)

        if not executor.registry.is_available("json_completion"):
            context.stay_recommendation_plan = self._fallback_plan(context, "OpenAI API key is not configured.")
            return context

        prompt = build_stay_recommendation_prompt(
            request=context.request,
            research_signals=context.research_signals,
            destination_research_summary=context.destination_research.summary
            if context.destination_research
            else "No destination research summary available.",
            destination_research_areas=context.destination_research.recommended_areas
            if context.destination_research
            else [],
            itinerary_days=[day.model_dump() for day in context.itinerary_plan.days],
            web_research_summary=self._combine_stay_research_summaries(
                str(tavily_bundle.get("summary", "No web research available.")),
                str(hotel_bundle.get("summary", "No structured hotel inventory available.")),
                str(tripadvisor_bundle.get("summary", "No Tripadvisor traveler context available.")),
            ),
        )

        try:
            payload = executor.execute(
                "json_completion",
                JsonCompletionInput(
                    developer_prompt=STAY_RECOMMENDATION_DEVELOPER_PROMPT,
                    user_prompt=prompt,
                ),
            ).payload
            plan = self._coerce_plan(
                context,
                payload,
                str(hotel_bundle.get("summary", "")),
                str(tripadvisor_bundle.get("summary", "")),
            )
        except (ResearchClientError, ValidationError) as exc:
            plan = self._fallback_plan(context, str(exc))

        context.stay_recommendation_plan = plan
        return context

    def _gather_web_research(self, context: PlannerContext, executor) -> dict[str, object]:
        if not executor.registry.is_available("web_search"):
            return {"summary": "Tavily API key is not configured."}

        request = context.request
        queries = [
            f"{request.destination} best hotels or homestays in {request.accommodation_preference or 'good traveler areas'}",
            f"{request.destination} safest neighborhoods to stay and hotel price ranges",
        ]
        try:
            result = executor.execute("web_search", WebSearchInput(queries=queries, max_results=3))
        except ResearchClientError as exc:
            return {"summary": f"Stay research failed: {exc}"}
        return {"summary": result.summary}

    def _gather_hotel_inventory(self, context: PlannerContext, executor) -> dict[str, object]:
        if not executor.registry.is_available("google_hotels_search"):
            return {"summary": "SerpApi hotel enrichment is not configured."}

        request = context.request
        try:
            result = executor.execute(
                "google_hotels_search",
                GoogleHotelsInput(
                    query=f"{request.destination} {request.accommodation_preference or 'traveler stay'}",
                    check_in_date=request.start_date,
                    check_out_date=request.end_date,
                    adults=request.traveler_count,
                    currency="INR",
                    gl="in",
                    hl="en",
                ),
            )
        except ResearchClientError as exc:
            return {"summary": f"Structured hotel inventory lookup failed: {exc}"}
        return {"summary": result.summary, "properties": [item.model_dump() for item in result.properties]}

    def _gather_tripadvisor_context(self, context: PlannerContext, executor) -> dict[str, object]:
        if not executor.registry.is_available("tripadvisor_search"):
            return {"summary": "SerpApi Tripadvisor enrichment is not configured."}

        request = context.request
        try:
            result = executor.execute(
                "tripadvisor_search",
                TripadvisorSearchInput(
                    query=f"{request.destination} {request.accommodation_preference or 'hotels and areas'}",
                    location=request.destination,
                    hl="en",
                ),
            )
        except ResearchClientError as exc:
            return {"summary": f"Tripadvisor traveler context lookup failed: {exc}"}
        return {"summary": result.summary, "results": [item.model_dump() for item in result.results]}

    def _combine_stay_research_summaries(
        self,
        web_summary: str,
        hotel_summary: str,
        tripadvisor_summary: str,
    ) -> str:
        return (
            f"General web research:\n{web_summary}\n\n"
            f"Structured hotel inventory:\n{hotel_summary}\n\n"
            f"Tripadvisor traveler context:\n{tripadvisor_summary}"
        ).strip()

    def _coerce_plan(
        self,
        context: PlannerContext,
        payload: dict[str, object],
        hotel_summary: str,
        tripadvisor_summary: str,
    ) -> StayRecommendationPlan:
        raw_recommendations = payload.get("recommendations")
        recommendations = []
        if isinstance(raw_recommendations, list):
            for item in raw_recommendations[:4]:
                if not isinstance(item, dict):
                    continue
                area = str(item.get("area") or self._default_area(context)).strip()
                name = str(item.get("name") or "Recommended stay").strip()
                recommendations.append(
                    StayRecommendation(
                        name=name,
                        stay_type=str(item.get("stay_type") or "hotel").strip(),
                        area=area,
                        price_band=str(item.get("price_band") or self._default_price_band(context)).strip(),
                        why_fit=str(item.get("why_fit") or "Chosen for itinerary fit and neighborhood access.").strip(),
                        safety_notes=self._coerce_list(item.get("safety_notes")),
                        booking_tips=self._coerce_list(item.get("booking_tips")),
                        booking_url=self._coerce_url(item.get("booking_url"))
                        or self._build_booking_url(context, name, area),
                        maps_url=self._coerce_url(item.get("maps_url")) or self._build_maps_url(context, name, area),
                        official_website=self._coerce_url(item.get("official_website")),
                    )
                )

        if not recommendations:
            return self._fallback_plan(context, "Model returned no stay recommendations.")

        return StayRecommendationPlan(
            destination=context.request.destination,
            summary=str(
                payload.get("summary") or f"Stay recommendations prepared for {context.request.destination}."
            ).strip(),
            hotel_inventory_summary=self._normalize_provider_summary(
                hotel_summary,
                "No structured hotel inventory signal was available."
            ),
            traveler_review_summary=self._normalize_provider_summary(
                tripadvisor_summary,
                "No traveler review signal was available."
            ),
            recommendations=recommendations,
            confidence=self._coerce_confidence(payload.get("confidence")),
        )

    def _fallback_plan(self, context: PlannerContext, reason: str) -> StayRecommendationPlan:
        area = self._default_area(context)
        return StayRecommendationPlan(
            destination=context.request.destination,
            summary="Fallback stay recommendations created because the primary stay recommendation step was unavailable.",
            hotel_inventory_summary="Structured hotel inventory was unavailable for this fallback stay plan.",
            traveler_review_summary=f"Traveler review enrichment fallback used because: {reason}",
            recommendations=[
                StayRecommendation(
                    name=f"{area} stay cluster",
                    stay_type=context.request.accommodation_preference or "hotel",
                    area=area,
                    price_band=self._default_price_band(context),
                    why_fit="Keeps the itinerary centered around the strongest recommended area.",
                    safety_notes=["Choose properties with strong recent reviews and late check-in clarity."],
                    booking_tips=[f"Fallback stay recommendation used because: {reason}"],
                    booking_url=self._build_booking_url(context, f"{area} stay cluster", area),
                    maps_url=self._build_maps_url(context, f"{area} stay cluster", area),
                )
            ],
            confidence=0.25,
        )

    def _normalize_provider_summary(self, summary: object, fallback: str) -> str:
        if isinstance(summary, str):
            cleaned = " ".join(summary.split()).strip()
            if cleaned:
                return cleaned
        return fallback

    def _default_area(self, context: PlannerContext) -> str:
        if context.destination_research and context.destination_research.recommended_areas:
            return context.destination_research.recommended_areas[0]
        return context.request.destination

    def _default_price_band(self, context: PlannerContext) -> str:
        return f"{context.request.budget_tier.value} estimated price band"

    def _coerce_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _coerce_url(self, value: object) -> str:
        if not isinstance(value, str):
            return ""
        cleaned = value.strip()
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        return ""

    def _build_booking_url(self, context: PlannerContext, name: str, area: str) -> str:
        return _build_booking_search_url(f"{name} {area} {context.request.destination}")

    def _build_maps_url(self, context: PlannerContext, name: str, area: str) -> str:
        return _build_google_maps_url(f"{name} {area} {context.request.destination}")

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))


@dataclass
class LocalTransportAgent:
    name: str = "local_transport_agent"

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        executor = build_tool_executor(context, self.name)

        if context.itinerary_plan is None:
            context.local_transport_plan = self._fallback_plan(
                context,
                "Itinerary plan is required before local transport guidance.",
            )
            return context

        tavily_bundle = self._gather_web_research(context, executor)

        if not executor.registry.is_available("json_completion"):
            context.local_transport_plan = self._fallback_plan(context, "OpenAI API key is not configured.")
            return context

        prompt = build_local_transport_prompt(
            request=context.request,
            research_signals=context.research_signals,
            destination_research_summary=context.destination_research.summary
            if context.destination_research
            else "No destination research summary available.",
            transport_notes=context.destination_research.local_transport_notes if context.destination_research else [],
            itinerary_days=[day.model_dump() for day in context.itinerary_plan.days],
            web_research_summary=str(tavily_bundle.get("summary", "No web research available.")),
        )

        try:
            payload = executor.execute(
                "json_completion",
                JsonCompletionInput(
                    developer_prompt=LOCAL_TRANSPORT_DEVELOPER_PROMPT,
                    user_prompt=prompt,
                ),
            ).payload
            plan = self._coerce_plan(context, payload)
        except (ResearchClientError, ValidationError) as exc:
            plan = self._fallback_plan(context, str(exc))

        context.local_transport_plan = plan
        return context

    def _gather_web_research(self, context: PlannerContext, executor) -> dict[str, object]:
        if not executor.registry.is_available("web_search"):
            return {"summary": "Tavily API key is not configured."}

        request = context.request
        queries = [
            f"{request.destination} metro bus taxi fares and local transport options for tourists",
            f"{request.destination} airport to city transport and common intra-city travel times",
        ]
        try:
            result = executor.execute("web_search", WebSearchInput(queries=queries, max_results=3))
        except ResearchClientError as exc:
            return {"summary": f"Transport research failed: {exc}"}
        return {"summary": result.summary}

    def _coerce_plan(self, context: PlannerContext, payload: dict[str, object]) -> LocalTransportPlan:
        raw_legs = payload.get("legs")
        legs = []
        if isinstance(raw_legs, list):
            for index, item in enumerate(raw_legs[: max(1, len(context.itinerary_plan.days))]):
                if not isinstance(item, dict):
                    continue
                legs.append(
                    TransportLegRecommendation(
                        day_number=int(item.get("day_number") or index + 1),
                        from_area=str(item.get("from_area") or self._default_area(context)).strip(),
                        to_area=str(item.get("to_area") or self._default_area(context)).strip(),
                        recommended_mode=str(item.get("recommended_mode") or self._default_mode(context)).strip(),
                        backup_mode=str(item.get("backup_mode") or "Taxi or ride-hailing").strip(),
                        approx_duration=str(item.get("approx_duration") or "20-40 minutes").strip(),
                        approx_fare=str(item.get("approx_fare") or "Low to moderate local fare").strip(),
                        notes=str(
                            item.get("notes") or "Use the most direct route during the busiest travel window."
                        ).strip(),
                    )
                )

        if not legs:
            return self._fallback_plan(context, "Model returned no transport guidance.")

        return LocalTransportPlan(
            destination=context.request.destination,
            summary=str(
                payload.get("summary") or f"Local transport guidance prepared for {context.request.destination}."
            ).strip(),
            legs=legs,
            confidence=self._coerce_confidence(payload.get("confidence")),
        )

    def _fallback_plan(self, context: PlannerContext, reason: str) -> LocalTransportPlan:
        area = self._default_area(context)
        return LocalTransportPlan(
            destination=context.request.destination,
            summary="Fallback local transport guidance created because the primary transport step was unavailable.",
            legs=[
                TransportLegRecommendation(
                    day_number=1,
                    from_area=area,
                    to_area=area,
                    recommended_mode=self._default_mode(context),
                    backup_mode="Taxi or ride-hailing",
                    approx_duration="15-30 minutes within the core area",
                    approx_fare="Low to moderate local fare",
                    notes=f"Fallback transport guidance used because: {reason}",
                )
            ],
            confidence=0.25,
        )

    def _default_area(self, context: PlannerContext) -> str:
        if context.destination_research and context.destination_research.recommended_areas:
            return context.destination_research.recommended_areas[0]
        return context.request.destination

    def _default_mode(self, context: PlannerContext) -> str:
        return context.request.transport_preference or "Public transit"

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))


@dataclass
class FoodRecommendationAgent:
    name: str = "food_recommendation_agent"

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        executor = build_tool_executor(context, self.name)

        if context.itinerary_plan is None:
            context.food_recommendation_plan = self._fallback_plan(
                context,
                "Itinerary plan is required before food recommendations.",
            )
            return context

        tavily_bundle = self._gather_web_research(context, executor)
        tripadvisor_bundle = self._gather_tripadvisor_context(context, executor)

        if not executor.registry.is_available("json_completion"):
            context.food_recommendation_plan = self._fallback_plan(context, "OpenAI API key is not configured.")
            return context

        prompt = build_food_recommendation_prompt(
            request=context.request,
            research_signals=context.research_signals,
            destination_research_summary=context.destination_research.summary
            if context.destination_research
            else "No destination research summary available.",
            itinerary_days=[day.model_dump() for day in context.itinerary_plan.days],
            web_research_summary=self._combine_food_research_summaries(
                str(tavily_bundle.get("summary", "No web research available.")),
                str(tripadvisor_bundle.get("summary", "No Tripadvisor traveler context available.")),
            ),
        )

        try:
            payload = executor.execute(
                "json_completion",
                JsonCompletionInput(
                    developer_prompt=FOOD_RECOMMENDATION_DEVELOPER_PROMPT,
                    user_prompt=prompt,
                ),
            ).payload
            plan = self._coerce_plan(
                context,
                payload,
                str(tripadvisor_bundle.get("summary", "No Tripadvisor traveler context available.")),
            )
        except (ResearchClientError, ValidationError) as exc:
            plan = self._fallback_plan(context, str(exc))

        context.food_recommendation_plan = plan
        return context

    def _gather_web_research(self, context: PlannerContext, executor) -> dict[str, object]:
        if not executor.registry.is_available("web_search"):
            return {"summary": "Tavily API key is not configured."}

        request = context.request
        queries = [
            f"{request.destination} best local food areas and cafes for travelers",
            f"{request.destination} vegetarian friendly restaurants street food and meal price ranges",
        ]
        try:
            result = executor.execute("web_search", WebSearchInput(queries=queries, max_results=3))
        except ResearchClientError as exc:
            return {"summary": f"Food research failed: {exc}"}
        return {"summary": result.summary}

    def _gather_tripadvisor_context(self, context: PlannerContext, executor) -> dict[str, object]:
        if not executor.registry.is_available("tripadvisor_search"):
            return {"summary": "SerpApi Tripadvisor enrichment is not configured."}

        request = context.request
        try:
            result = executor.execute(
                "tripadvisor_search",
                TripadvisorSearchInput(
                    query=f"{request.destination} best restaurants and local food",
                    location=request.destination,
                    hl="en",
                ),
            )
        except ResearchClientError as exc:
            return {"summary": f"Tripadvisor food context lookup failed: {exc}"}
        return {"summary": result.summary, "results": [item.model_dump() for item in result.results]}

    def _combine_food_research_summaries(self, web_summary: str, tripadvisor_summary: str) -> str:
        return (
            f"General web research:\n{web_summary}\n\n"
            f"Tripadvisor traveler context:\n{tripadvisor_summary}"
        ).strip()

    def _coerce_plan(
        self,
        context: PlannerContext,
        payload: dict[str, object],
        tripadvisor_summary: str,
    ) -> FoodRecommendationPlan:
        raw_recommendations = payload.get("recommendations")
        recommendations = []
        if isinstance(raw_recommendations, list):
            for item in raw_recommendations[: max(3, len(context.itinerary_plan.days) * 2)]:
                if not isinstance(item, dict):
                    continue
                venue_name = str(item.get("venue_name") or "Recommended local venue").strip()
                area = str(item.get("area") or self._default_area(context)).strip()
                recommendations.append(
                    FoodRecommendation(
                        day_number=int(item.get("day_number") or 1),
                        meal=str(item.get("meal") or "meal").strip(),
                        venue_name=venue_name,
                        area=area,
                        cuisine_type=str(item.get("cuisine_type") or "Local cuisine").strip(),
                        price_level=str(item.get("price_level") or context.request.budget_tier.value).strip(),
                        dietary_fit=str(item.get("dietary_fit") or "Check menu fit locally").strip(),
                        why_fit=str(item.get("why_fit") or "Fits the itinerary area and local food goals.").strip(),
                        maps_url=self._coerce_url(item.get("maps_url"))
                        or self._build_maps_url(context, venue_name, area),
                        official_website=self._coerce_url(item.get("official_website")),
                        review_video_urls=self._coerce_url_list(item.get("review_video_urls"))[:3]
                        or self._default_review_video_urls(context, venue_name),
                    )
                )

        if not recommendations:
            return self._fallback_plan(context, "Model returned no food recommendations.")

        return FoodRecommendationPlan(
            destination=context.request.destination,
            summary=str(
                payload.get("summary") or f"Food recommendations prepared for {context.request.destination}."
            ).strip(),
            traveler_review_summary=self._normalize_provider_summary(
                tripadvisor_summary,
                "No traveler food review signal was available."
            ),
            recommendations=recommendations,
            confidence=self._coerce_confidence(payload.get("confidence")),
        )

    def _fallback_plan(self, context: PlannerContext, reason: str) -> FoodRecommendationPlan:
        return FoodRecommendationPlan(
            destination=context.request.destination,
            summary="Fallback food recommendations created because the primary food recommendation step was unavailable.",
            traveler_review_summary=f"Traveler food review fallback used because: {reason}",
            recommendations=[
                FoodRecommendation(
                    day_number=1,
                    meal="dinner",
                    venue_name="Well-reviewed local dining area",
                    area=self._default_area(context),
                    cuisine_type="Local specialties",
                    price_level=context.request.budget_tier.value,
                    dietary_fit="Confirm dietary fit on arrival",
                    why_fit=f"Fallback food recommendation used because: {reason}",
                    maps_url=self._build_maps_url(
                        context,
                        "Well-reviewed local dining area",
                        self._default_area(context),
                    ),
                    official_website="",
                    review_video_urls=self._default_review_video_urls(
                        context,
                        "Well-reviewed local dining area",
                    ),
                )
            ],
            confidence=0.25,
        )

    def _normalize_provider_summary(self, summary: object, fallback: str) -> str:
        if isinstance(summary, str):
            cleaned = " ".join(summary.split()).strip()
            if cleaned:
                return cleaned
        return fallback

    def _default_area(self, context: PlannerContext) -> str:
        if context.destination_research and context.destination_research.recommended_areas:
            return context.destination_research.recommended_areas[0]
        return context.request.destination

    def _coerce_url(self, value: object) -> str:
        if not isinstance(value, str):
            return ""
        cleaned = value.strip()
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        return ""

    def _coerce_url_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        urls: list[str] = []
        for item in value:
            url = self._coerce_url(item)
            if url and url not in urls:
                urls.append(url)
        return urls

    def _build_maps_url(self, context: PlannerContext, venue_name: str, area: str) -> str:
        return _build_google_maps_url(f"{venue_name} {area} {context.request.destination}")

    def _default_review_video_urls(self, context: PlannerContext, venue_name: str) -> list[str]:
        return [
            _build_youtube_search_url(
                f"{venue_name} {context.request.destination} food review shorts"
            )
        ]

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))


@dataclass
class BudgetOptimizationAgent:
    name: str = "budget_optimization_agent"

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        executor = build_tool_executor(context, self.name)

        if context.itinerary_plan is None:
            context.budget_assessment = self._fallback_assessment(
                context,
                "Itinerary plan is required before budget optimization.",
            )
            context.status = TripStatus.BUDGET_WARNING
            return context

        if not executor.registry.is_available("json_completion"):
            context.budget_assessment = self._fallback_assessment(context, "OpenAI API key is not configured.")
            context.status = TripStatus.BUDGET_WARNING
            return context

        destination_summary = (
            context.destination_research.summary
            if context.destination_research is not None
            else "No destination research summary available."
        )
        stay_summary = (
            context.stay_recommendation_plan.summary
            if context.stay_recommendation_plan is not None
            else "No stay recommendation summary available."
        )
        local_transport_summary = (
            context.local_transport_plan.summary
            if context.local_transport_plan is not None
            else "No local transport summary available."
        )
        food_summary = (
            context.food_recommendation_plan.summary
            if context.food_recommendation_plan is not None
            else "No food recommendation summary available."
        )
        itinerary_days = [day.model_dump() for day in context.itinerary_plan.days]
        prompt = build_budget_optimization_prompt(
            request=context.request,
            research_signals=context.research_signals,
            destination_research_summary=destination_summary,
            itinerary_summary=context.itinerary_plan.summary,
            itinerary_days=itinerary_days,
            stay_summary=stay_summary,
            local_transport_summary=local_transport_summary,
            food_summary=food_summary,
        )

        try:
            payload = executor.execute(
                "json_completion",
                JsonCompletionInput(
                    developer_prompt=BUDGET_OPTIMIZATION_DEVELOPER_PROMPT,
                    user_prompt=prompt,
                ),
            ).payload
            assessment = self._coerce_budget_assessment(context, payload)
        except (ResearchClientError, ValidationError) as exc:
            assessment = self._fallback_assessment(context, str(exc))

        context.budget_assessment = assessment
        context.budget_warnings = assessment.warnings
        context.status = TripStatus.READY_FOR_REVIEW if assessment.within_budget else TripStatus.BUDGET_WARNING
        return context

    def _coerce_budget_assessment(self, context: PlannerContext, payload: dict[str, object]) -> BudgetAssessment:
        within_budget = payload.get("within_budget")
        within_budget_bool = within_budget if isinstance(within_budget, bool) else False
        return BudgetAssessment(
            destination=context.request.destination,
            within_budget=within_budget_bool,
            estimated_total_cost=str(
                payload.get("estimated_total_cost") or f"Target total budget is {context.request.total_budget}."
            ).strip(),
            estimated_daily_cost=str(payload.get("estimated_daily_cost") or self._default_daily_cost(context)).strip(),
            summary=str(
                payload.get("summary") or "Budget assessment generated from itinerary and destination research."
            ).strip(),
            cost_drivers=self._coerce_list(payload.get("cost_drivers")),
            optimization_actions=self._coerce_list(payload.get("optimization_actions")),
            warnings=self._coerce_list(payload.get("warnings")),
            confidence=self._coerce_confidence(payload.get("confidence")),
        )

    def _fallback_assessment(self, context: PlannerContext, reason: str) -> BudgetAssessment:
        budget_per_day = self._default_daily_cost(context)
        return BudgetAssessment(
            destination=context.request.destination,
            within_budget=False,
            estimated_total_cost=f"Budget target: {context.request.total_budget}",
            estimated_daily_cost=budget_per_day,
            summary="Fallback budget assessment created because the main optimization step was unavailable.",
            cost_drivers=[
                "Accommodation and transport are likely the primary cost drivers.",
                "Activity intensity and dining choices can materially change daily spend.",
            ],
            optimization_actions=[
                "Keep one low-cost or free activity block per day.",
                "Concentrate activities by area to reduce transport spend.",
            ],
            warnings=[f"Fallback budget assessment used because: {reason}"],
            confidence=0.25,
        )

    def _default_daily_cost(self, context: PlannerContext) -> str:
        budget = context.research_signals.get("budget_per_day")
        if isinstance(budget, (int, float)):
            return f"Approximately {round(float(budget), 2)} total per day"
        return "Estimated from total budget and trip length"

    def _coerce_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))


@dataclass
class SoloWomenSafetyAdvisorAgent:
    name: str = "solo_women_safety_advisor_agent"

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        executor = build_tool_executor(context, self.name)

        if context.itinerary_plan is None:
            context.solo_women_safety_assessment = self._fallback_assessment(
                context,
                "Itinerary plan is required before creating a safety advisory.",
            )
            return context

        if not executor.registry.is_available("json_completion"):
            context.solo_women_safety_assessment = self._fallback_assessment(
                context,
                "OpenAI API key is not configured.",
            )
            return context

        destination_summary = (
            context.destination_research.summary
            if context.destination_research is not None
            else "No destination research summary available."
        )
        destination_areas = (
            context.destination_research.recommended_areas if context.destination_research is not None else []
        )
        destination_risks = context.destination_research.top_risks if context.destination_research is not None else []
        itinerary_days = [day.model_dump() for day in context.itinerary_plan.days]
        prompt = build_solo_women_safety_prompt(
            request=context.request,
            research_signals=context.research_signals,
            destination_research_summary=destination_summary,
            destination_research_areas=destination_areas,
            destination_risks=destination_risks,
            itinerary_days=itinerary_days,
        )

        try:
            payload = executor.execute(
                "json_completion",
                JsonCompletionInput(
                    developer_prompt=SOLO_WOMEN_SAFETY_DEVELOPER_PROMPT,
                    user_prompt=prompt,
                ),
            ).payload
            assessment = self._coerce_assessment(context, payload)
        except (ResearchClientError, ValidationError) as exc:
            assessment = self._fallback_assessment(context, str(exc))

        context.solo_women_safety_assessment = assessment
        return context

    def _coerce_assessment(self, context: PlannerContext, payload: dict[str, object]) -> SoloWomenSafetyAssessment:
        applies = payload.get("applies")
        applies_bool = applies if isinstance(applies, bool) else context.request.traveler_count == 1
        return SoloWomenSafetyAssessment(
            destination=context.request.destination,
            applies=applies_bool,
            summary=str(payload.get("summary") or "Safety advisory generated for this trip plan.").strip(),
            solo_traveler_fit=str(payload.get("solo_traveler_fit") or self._default_solo_fit(context)).strip(),
            women_safety_risk_level=str(payload.get("women_safety_risk_level") or "moderate").strip(),
            safe_areas=self._coerce_list(payload.get("safe_areas")),
            caution_areas=self._coerce_list(payload.get("caution_areas")),
            night_transport_guidance=self._coerce_list(payload.get("night_transport_guidance")),
            lodging_safety_tips=self._coerce_list(payload.get("lodging_safety_tips")),
            solo_friendly_suggestions=self._coerce_list(payload.get("solo_friendly_suggestions")),
            itinerary_adjustments=self._coerce_list(payload.get("itinerary_adjustments")),
            confidence=self._coerce_confidence(payload.get("confidence")),
        )

    def _fallback_assessment(self, context: PlannerContext, reason: str) -> SoloWomenSafetyAssessment:
        area = self._default_area(context)
        return SoloWomenSafetyAssessment(
            destination=context.request.destination,
            applies=context.request.traveler_count == 1,
            summary="Fallback solo and women's safety advisory created because the primary advisory step was unavailable.",
            solo_traveler_fit=self._default_solo_fit(context),
            women_safety_risk_level="moderate",
            safe_areas=[area] if area else [],
            caution_areas=[],
            night_transport_guidance=[
                "Prefer direct registered transport options after dark.",
                "Avoid last-minute route changes when returning late.",
            ],
            lodging_safety_tips=[
                "Choose well-reviewed lodging in an active area with reliable late return options.",
                "Share itinerary checkpoints with a trusted contact when traveling solo.",
            ],
            solo_friendly_suggestions=[
                "Keep one flexible daytime activity block that is easy to exit or shorten.",
                "Prioritize neighborhoods with strong foot traffic and straightforward transit access.",
            ],
            itinerary_adjustments=[f"Fallback advisory used because: {reason}"],
            confidence=0.25,
        )

    def _default_area(self, context: PlannerContext) -> str:
        if context.destination_research and context.destination_research.recommended_areas:
            return context.destination_research.recommended_areas[0]
        return context.request.destination

    def _default_solo_fit(self, context: PlannerContext) -> str:
        return "strong fit" if context.request.traveler_count == 1 else "general guidance"

    def _coerce_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))


@dataclass
class ReviewAndConsistencyAgent:
    name: str = "review_and_consistency_agent"

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        executor = build_tool_executor(context, self.name)

        if context.itinerary_plan is None:
            context.review_assessment = self._fallback_review(
                context,
                "Itinerary plan is required before review.",
            )
            context.review_notes = context.review_assessment.issues
            return context

        if not executor.registry.is_available("json_completion"):
            context.review_assessment = self._fallback_review(context, "OpenAI API key is not configured.")
            context.review_notes = context.review_assessment.issues
            return context

        destination_summary = (
            context.destination_research.summary
            if context.destination_research is not None
            else "No destination research summary available."
        )
        budget_summary = (
            context.budget_assessment.summary
            if context.budget_assessment is not None
            else "No budget assessment summary available."
        )
        safety_summary = (
            context.solo_women_safety_assessment.summary
            if context.solo_women_safety_assessment is not None
            else "No solo traveler or women's safety advisory available."
        )
        stay_summary = (
            context.stay_recommendation_plan.summary
            if context.stay_recommendation_plan is not None
            else "No stay recommendation summary available."
        )
        local_transport_summary = (
            context.local_transport_plan.summary
            if context.local_transport_plan is not None
            else "No local transport summary available."
        )
        food_summary = (
            context.food_recommendation_plan.summary
            if context.food_recommendation_plan is not None
            else "No food recommendation summary available."
        )
        itinerary_days = [day.model_dump() for day in context.itinerary_plan.days]
        prompt = build_review_and_consistency_prompt(
            request=context.request,
            research_signals=context.research_signals,
            destination_research_summary=destination_summary,
            itinerary_summary=context.itinerary_plan.summary,
            budget_summary=budget_summary,
            itinerary_days=itinerary_days,
            budget_warnings=context.budget_warnings,
            safety_summary=safety_summary,
            stay_summary=stay_summary,
            local_transport_summary=local_transport_summary,
            food_summary=food_summary,
        )

        try:
            payload = executor.execute(
                "json_completion",
                JsonCompletionInput(
                    developer_prompt=REVIEW_AND_CONSISTENCY_DEVELOPER_PROMPT,
                    user_prompt=prompt,
                ),
            ).payload
            review = self._coerce_review_assessment(context, payload)
        except (ResearchClientError, ValidationError) as exc:
            review = self._fallback_review(context, str(exc))

        context.review_assessment = review
        context.review_notes = review.issues
        context.status = TripStatus.COMPLETED if review.approved else TripStatus.READY_FOR_REVIEW
        return context

    def _coerce_review_assessment(self, context: PlannerContext, payload: dict[str, object]) -> ReviewAssessment:
        approved = payload.get("approved")
        approved_bool = approved if isinstance(approved, bool) else False
        return ReviewAssessment(
            destination=context.request.destination,
            approved=approved_bool,
            summary=str(payload.get("summary") or "Review completed for the proposed trip plan.").strip(),
            consistency_score=self._coerce_confidence(payload.get("consistency_score")),
            strengths=self._coerce_list(payload.get("strengths")),
            issues=self._coerce_list(payload.get("issues")),
            recommended_fixes=self._coerce_list(payload.get("recommended_fixes")),
            final_notes=self._coerce_list(payload.get("final_notes")),
            confidence=self._coerce_confidence(payload.get("confidence")),
        )

    def _fallback_review(self, context: PlannerContext, reason: str) -> ReviewAssessment:
        issues = [f"Fallback review used because: {reason}"]
        if context.budget_assessment and not context.budget_assessment.within_budget:
            issues.append("Budget assessment indicates the itinerary may exceed the intended spend profile.")
        return ReviewAssessment(
            destination=context.request.destination,
            approved=False,
            summary="Fallback review created because the primary consistency review step was unavailable.",
            consistency_score=0.25,
            strengths=[
                "The plan has a structured itinerary draft.",
                "Destination research and budget review data are available for manual inspection.",
            ],
            issues=issues,
            recommended_fixes=[
                "Review pacing and budget tradeoffs before treating this plan as final.",
                "Re-run the review step once the model service is available.",
            ],
            final_notes=["Manual approval is recommended before presenting this itinerary as final."],
            confidence=0.25,
        )

    def _coerce_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, confidence))


@dataclass
class GovernanceGateAgent:
    name: str = "governance_gate_agent"

    def run(self, context: PlannerContext) -> PlannerContext:
        context.mark(self.name)
        decision = evaluate_governance(context)
        context.governance_flags = decision.flags
        context.run_summary["governance"] = {
            "approve": decision.approve,
            "flags": decision.flags,
        }
        if context.review_assessment is not None:
            if decision.flags:
                context.review_assessment.approved = False
                context.review_assessment.issues = sorted(set(context.review_assessment.issues + decision.flags))
            context.status = TripStatus.COMPLETED if decision.approve else TripStatus.READY_FOR_REVIEW
        else:
            context.status = TripStatus.READY_FOR_REVIEW
        return context
