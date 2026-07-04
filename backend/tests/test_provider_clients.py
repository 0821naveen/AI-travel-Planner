from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from src.providers.search import SerpApiClient, TavilyClient
from src.providers.travel import AviationstackClient


def test_tavily_client_posts_expected_payload(monkeypatch):
    captured: dict[str, object] = {}

    def fake_json_request(*, method, url, headers=None, payload=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {"answer": "ok", "results": []}

    monkeypatch.setattr("src.providers.search.json_request", fake_json_request)

    client = TavilyClient(api_key="tavily-key")
    response = client.search("best darjeeling toy train plan", max_results=3)

    assert response["answer"] == "ok"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"] == {"Authorization": "Bearer tavily-key"}
    assert captured["payload"] == {
        "query": "best darjeeling toy train plan",
        "topic": "general",
        "search_depth": "advanced",
        "chunks_per_source": 2,
        "max_results": 3,
        "include_answer": "advanced",
        "include_raw_content": "text",
    }


def test_serpapi_google_flights_client_builds_expected_query(monkeypatch):
    captured: dict[str, object] = {}

    def fake_json_request(*, method, url, headers=None, payload=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {"best_flights": []}

    monkeypatch.setattr("src.providers.search.json_request", fake_json_request)

    client = SerpApiClient(api_key="serp-key")
    response = client.google_flights(
        departure_id="BLR",
        arrival_id="IXB",
        outbound_date="2026-12-10",
        return_date="2026-12-15",
        adults=2,
        children=1,
        currency="INR",
        hl="en",
        gl="in",
        travel_class=2,
    )

    assert response["best_flights"] == []
    assert captured["method"] == "GET"
    parsed = urlparse(str(captured["url"]))
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "serpapi.com"
    assert params["engine"] == ["google_flights"]
    assert params["api_key"] == ["serp-key"]
    assert params["departure_id"] == ["BLR"]
    assert params["arrival_id"] == ["IXB"]
    assert params["outbound_date"] == ["2026-12-10"]
    assert params["return_date"] == ["2026-12-15"]
    assert params["adults"] == ["2"]
    assert params["children"] == ["1"]
    assert params["currency"] == ["INR"]
    assert params["travel_class"] == ["2"]


def test_serpapi_google_hotels_client_builds_expected_query(monkeypatch):
    captured: dict[str, object] = {}

    def fake_json_request(*, method, url, headers=None, payload=None):
        captured["url"] = url
        return {"properties": []}

    monkeypatch.setattr("src.providers.search.json_request", fake_json_request)

    client = SerpApiClient(api_key="serp-key")
    client.google_hotels(
        query="darjeeling hotels",
        check_in_date="2026-10-01",
        check_out_date="2026-10-03",
        adults=2,
        children=0,
    )

    params = parse_qs(urlparse(str(captured["url"])).query)
    assert params["engine"] == ["google_hotels"]
    assert params["q"] == ["darjeeling hotels"]
    assert params["check_in_date"] == ["2026-10-01"]
    assert params["check_out_date"] == ["2026-10-03"]
    assert params["currency"] == ["INR"]


def test_serpapi_tripadvisor_client_builds_expected_query(monkeypatch):
    captured: dict[str, object] = {}

    def fake_json_request(*, method, url, headers=None, payload=None):
        captured["url"] = url
        return {"results": []}

    monkeypatch.setattr("src.providers.search.json_request", fake_json_request)

    client = SerpApiClient(api_key="serp-key")
    client.tripadvisor_search(query="best cafes in goa", location="Goa", hl="en")

    params = parse_qs(urlparse(str(captured["url"])).query)
    assert params["engine"] == ["tripadvisor"]
    assert params["q"] == ["best cafes in goa"]
    assert params["location"] == ["Goa"]
    assert params["hl"] == ["en"]


def test_aviationstack_client_builds_airport_and_flight_urls(monkeypatch):
    captured_urls: list[str] = []

    def fake_json_request(*, method, url, headers=None, payload=None):
        captured_urls.append(url)
        if "/airports?" in url:
            return {"data": []}
        return {"data": []}

    monkeypatch.setattr("src.providers.travel.json_request", fake_json_request)

    client = AviationstackClient(api_key="aviation-key")
    client.airports("Bengaluru")
    client.flights(flight_date="2026-11-20", dep_iata="BLR", arr_iata="IXB")

    airports_params = parse_qs(urlparse(captured_urls[0]).query)
    flights_params = parse_qs(urlparse(captured_urls[1]).query)
    assert airports_params["access_key"] == ["aviation-key"]
    assert airports_params["search"] == ["Bengaluru"]
    assert flights_params["access_key"] == ["aviation-key"]
    assert flights_params["flight_date"] == ["2026-11-20"]
    assert flights_params["dep_iata"] == ["BLR"]
    assert flights_params["arr_iata"] == ["IXB"]
