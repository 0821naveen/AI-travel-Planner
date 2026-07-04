from __future__ import annotations

import pytest

from src.core.config import BACKEND_DIR, build_settings
from src.providers.base import ResearchClientError
from src.providers.search import SerpApiClient, TavilyClient
from src.providers.travel import AviationstackClient


def _skip_if_missing(*values: str | None) -> None:
    if not all(value and value.strip() for value in values):
        pytest.skip("Live provider smoke test skipped because one or more API keys are missing.")


def _live_settings():
    return build_settings(env_files=[str(BACKEND_DIR / ".env")])


def test_live_tavily_search_smoke():
    settings = _live_settings()
    _skip_if_missing(settings.tavily_api_key)

    tavily_client = TavilyClient(settings.tavily_api_key)

    response = tavily_client.search("best time to visit Darjeeling", max_results=2)

    assert "error" not in response
    assert isinstance(response.get("results", []), list)


def test_live_serpapi_google_flights_smoke():
    settings = _live_settings()
    _skip_if_missing(settings.serpapi_api_key)

    serpapi_client = SerpApiClient(settings.serpapi_api_key)

    response = serpapi_client.google_flights(
        departure_id="BLR",
        arrival_id="IXB",
        outbound_date="2026-12-10",
        return_date="2026-12-15",
        adults=1,
        children=0,
    )

    assert "error" not in response
    assert any(key in response for key in ("best_flights", "other_flights", "search_metadata"))


def test_live_serpapi_google_hotels_smoke():
    settings = _live_settings()
    _skip_if_missing(settings.serpapi_api_key)

    serpapi_client = SerpApiClient(settings.serpapi_api_key)

    response = serpapi_client.google_hotels(
        query="Darjeeling hotels",
        check_in_date="2026-12-10",
        check_out_date="2026-12-12",
        adults=2,
        children=0,
    )

    assert "error" not in response
    assert any(key in response for key in ("properties", "search_metadata"))


def test_live_serpapi_tripadvisor_smoke():
    settings = _live_settings()
    _skip_if_missing(settings.serpapi_api_key)

    serpapi_client = SerpApiClient(settings.serpapi_api_key)

    response = serpapi_client.tripadvisor_search(
        query="top restaurants in Darjeeling",
        location="Darjeeling",
        hl="en",
    )

    assert "error" not in response
    assert any(key in response for key in ("results", "search_metadata"))


def test_live_aviationstack_flights_smoke():
    settings = _live_settings()
    _skip_if_missing(settings.aviationstack_api_key)

    aviationstack_client = AviationstackClient(settings.aviationstack_api_key)

    try:
        response = aviationstack_client.flights(
            flight_date="2026-12-10",
            dep_iata="BLR",
            arr_iata="IXB",
        )
    except ResearchClientError as exc:
        if "function_access_restricted" in str(exc):
            pytest.xfail("Aviationstack key is valid, but the current subscription plan does not allow the flights endpoint.")
        raise

    assert "error" not in response
    assert isinstance(response.get("data", []), list)
