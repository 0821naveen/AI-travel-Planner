from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from urllib.parse import urlencode

from src.core.config import get_settings
from src.providers.base import json_request


@dataclass
class TavilyClient:
    api_key: str
    base_url: str = "https://api.tavily.com/search"

    def search(self, query: str, max_results: int = 4) -> Dict[str, Any]:
        settings = get_settings()
        resolved_max_results = max_results or settings.provider_runtime.tavily_max_results
        return json_request(
            method="POST",
            url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload={
                "query": query,
                "topic": "general",
                "search_depth": "advanced",
                "chunks_per_source": 2,
                "max_results": resolved_max_results,
                "include_answer": "advanced",
                "include_raw_content": "text",
            },
        )


@dataclass
class SerpApiClient:
    api_key: str
    base_url: str = "https://serpapi.com/search.json"

    def google_hotels(
        self,
        *,
        query: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        children: int = 0,
        gl: str = "in",
        hl: str = "en",
        currency: str = "INR",
    ) -> Dict[str, Any]:
        params = urlencode(
            {
                "engine": "google_hotels",
                "api_key": self.api_key,
                "q": query,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "adults": max(1, adults),
                "children": max(0, children),
                "gl": gl,
                "hl": hl,
                "currency": currency,
            }
        )
        return json_request(method="GET", url=f"{self.base_url}?{params}")

    def youtube_video(self, *, video_id: str, hl: str = "en") -> Dict[str, Any]:
        params = urlencode(
            {
                "engine": "youtube_video",
                "api_key": self.api_key,
                "v": video_id,
                "hl": hl,
            }
        )
        return json_request(method="GET", url=f"{self.base_url}?{params}")

    def tripadvisor_search(
        self,
        *,
        query: str,
        location: str = "",
        hl: str = "en",
    ) -> Dict[str, Any]:
        params = urlencode(
            {
                "engine": "tripadvisor",
                "api_key": self.api_key,
                "q": query,
                "location": location,
                "hl": hl,
            }
        )
        return json_request(method="GET", url=f"{self.base_url}?{params}")

    def google_flights(
        self,
        *,
        departure_id: str,
        arrival_id: str,
        outbound_date: str,
        return_date: str,
        adults: int = 1,
        children: int = 0,
        currency: str = "INR",
        hl: str = "en",
        gl: str = "in",
        travel_class: int = 1,
    ) -> Dict[str, Any]:
        params = urlencode(
            {
                "engine": "google_flights",
                "api_key": self.api_key,
                "departure_id": departure_id,
                "arrival_id": arrival_id,
                "outbound_date": outbound_date,
                "return_date": return_date,
                "adults": max(1, adults),
                "children": max(0, children),
                "currency": currency,
                "hl": hl,
                "gl": gl,
                "travel_class": travel_class,
            }
        )
        return json_request(method="GET", url=f"{self.base_url}?{params}")
