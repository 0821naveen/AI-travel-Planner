from __future__ import annotations

from src.agents.travel_planner.schemas import ResearchSource
from src.agents.travel_planner.tooling.base import (
    ToolAuthMethod,
    ToolMetadata,
    ToolSideEffectLevel,
    ToolUnavailableError,
    ToolUsage,
)
from src.agents.travel_planner.tooling.contracts import (
    GoogleFlightsBestFlight,
    GoogleFlightsInput,
    GoogleFlightsOutput,
    TripadvisorResult,
    TripadvisorSearchInput,
    TripadvisorSearchOutput,
    WebSearchInput,
    WebSearchOutput,
    sanitize_untrusted_text,
)
from src.providers.search import SerpApiClient, TavilyClient


class TavilyWebSearchTool:
    name = "web_search"
    metadata = ToolMetadata(
        name="web_search",
        description="Searches the web for destination research and returns summarized findings.",
        allowed_agents=(
            "destination_research_agent",
            "stay_recommendation_agent",
            "local_transport_agent",
            "food_recommendation_agent",
        ),
        provider_name="tavily",
        provider_endpoint="search",
        auth_method=ToolAuthMethod.API_KEY,
        timeout_seconds=15,
        retry_policy="retry_once",
        rate_limit_per_minute=30,
        side_effect_level=ToolSideEffectLevel.EXTERNAL_READ,
        input_model=WebSearchInput,
        output_model=WebSearchOutput,
    )

    def __init__(self, client: TavilyClient | None) -> None:
        self.client = client

    def is_available(self) -> bool:
        return self.client is not None

    def execute(self, payload: WebSearchInput) -> WebSearchOutput:
        if self.client is None:
            raise ToolUnavailableError("Tavily API key is not configured.")

        summaries: list[str] = []
        sources: list[ResearchSource] = []
        seen_urls: set[str] = set()

        for query in payload.queries:
            response = self.client.search(query, max_results=payload.max_results)
            answer = response.get("answer")
            if answer:
                summaries.append(f"Query: {query}\nAnswer: {sanitize_untrusted_text(str(answer))}")

            for result in response.get("results", [])[: payload.results_per_query]:
                url = result.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                snippet = (result.get("content") or result.get("raw_content") or "").strip()
                if not snippet:
                    snippet = "No content snippet returned."
                sources.append(
                    ResearchSource(
                        title=result.get("title") or "Untitled source",
                        url=url,
                        snippet=sanitize_untrusted_text(snippet[:600]),
                    )
                )

        return WebSearchOutput(summary="\n\n".join(summaries), sources=sources, usage=ToolUsage())


class SerpApiTripadvisorTool:
    name = "tripadvisor_search"
    metadata = ToolMetadata(
        name="tripadvisor_search",
        description="Fetches Tripadvisor search results through SerpApi for traveler-oriented stay and food context.",
        allowed_agents=("stay_recommendation_agent", "food_recommendation_agent"),
        provider_name="serpapi",
        provider_endpoint="tripadvisor",
        auth_method=ToolAuthMethod.API_KEY,
        timeout_seconds=20,
        retry_policy="retry_once",
        rate_limit_per_minute=20,
        side_effect_level=ToolSideEffectLevel.EXTERNAL_READ,
        input_model=TripadvisorSearchInput,
        output_model=TripadvisorSearchOutput,
    )

    def __init__(self, client: SerpApiClient | None) -> None:
        self.client = client

    def is_available(self) -> bool:
        return self.client is not None

    def execute(self, payload: TripadvisorSearchInput) -> TripadvisorSearchOutput:
        if self.client is None:
            raise ToolUnavailableError("SerpApi key is not configured.")
        response = self.client.tripadvisor_search(query=payload.query, location=payload.location, hl=payload.hl)
        results: list[TripadvisorResult] = []
        for item in response.get("results", [])[:5]:
            results.append(
                TripadvisorResult(
                    title=str(item.get("title") or "Untitled result").strip(),
                    link=str(item.get("link") or "").strip(),
                    rating=str(item.get("rating") or "").strip(),
                    reviews=str(item.get("reviews") or "").strip(),
                    category=str(item.get("category") or "").strip(),
                    snippet=str(item.get("snippet") or item.get("description") or "").strip(),
                )
            )
        summary = "; ".join(
            f"{item.title} | {item.rating or 'rating n/a'} | {item.category or 'category n/a'}"
            for item in results[:3]
        ) or "No Tripadvisor results returned."
        return TripadvisorSearchOutput(summary=summary, results=results, raw_payload=response, usage=ToolUsage())


class SerpApiGoogleFlightsTool:
    name = "google_flights_search"
    metadata = ToolMetadata(
        name="google_flights_search",
        description="Fetches Google Flights search results through SerpApi for flight price and schedule enrichment.",
        allowed_agents=("destination_research_agent",),
        provider_name="serpapi",
        provider_endpoint="google_flights",
        auth_method=ToolAuthMethod.API_KEY,
        timeout_seconds=20,
        retry_policy="retry_once",
        rate_limit_per_minute=20,
        side_effect_level=ToolSideEffectLevel.EXTERNAL_READ,
        input_model=GoogleFlightsInput,
        output_model=GoogleFlightsOutput,
    )

    def __init__(self, client: SerpApiClient | None) -> None:
        self.client = client

    def is_available(self) -> bool:
        return self.client is not None

    def execute(self, payload: GoogleFlightsInput) -> GoogleFlightsOutput:
        if self.client is None:
            raise ToolUnavailableError("SerpApi key is not configured.")
        response = self.client.google_flights(
            departure_id=payload.departure_id,
            arrival_id=payload.arrival_id,
            outbound_date=payload.outbound_date,
            return_date=payload.return_date,
            adults=payload.adults,
            children=payload.children,
            currency=payload.currency,
            hl=payload.hl,
            gl=payload.gl,
            travel_class=payload.travel_class,
        )
        best_flights: list[GoogleFlightsBestFlight] = []
        for item in response.get("best_flights", [])[:3]:
            flights = item.get("flights") or []
            first_leg = flights[0] if flights else {}
            last_leg = flights[-1] if flights else {}
            best_flights.append(
                GoogleFlightsBestFlight(
                    airline=str(first_leg.get("airline") or "").strip(),
                    price=str(item.get("price") or "").strip(),
                    total_duration=str(item.get("total_duration") or "").strip(),
                    departure_airport=str(first_leg.get("departure_airport", {}).get("name") or "").strip(),
                    arrival_airport=str(last_leg.get("arrival_airport", {}).get("name") or "").strip(),
                )
            )
        summary = "; ".join(
            f"{item.airline or 'Airline n/a'} | {item.price or 'price n/a'} | {item.total_duration or 'duration n/a'}"
            for item in best_flights
        ) or "No Google Flights results returned."
        return GoogleFlightsOutput(summary=summary, best_flights=best_flights, raw_payload=response, usage=ToolUsage())
