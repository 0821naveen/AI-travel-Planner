from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from urllib.parse import urlencode

from src.core.config import get_settings
from src.providers.base import json_request


@dataclass
class WeatherApiClient:
    api_key: str
    base_url: str = "https://api.weatherapi.com/v1"

    def current(self, location: str) -> Dict[str, Any]:
        query = urlencode({"key": self.api_key, "q": location, "aqi": "no"})
        return json_request(method="GET", url=f"{self.base_url}/current.json?{query}")

    def forecast(self, location: str, days: int) -> Dict[str, Any]:
        settings = get_settings()
        max_days = settings.provider_runtime.weather_forecast_max_days
        query = urlencode(
            {"key": self.api_key, "q": location, "days": max(1, min(days, max_days)), "aqi": "no", "alerts": "no"}
        )
        return json_request(method="GET", url=f"{self.base_url}/forecast.json?{query}")


@dataclass
class AviationstackClient:
    api_key: str
    base_url: str = "https://api.aviationstack.com/v1"

    def airports(self, search: str) -> Dict[str, Any]:
        query = urlencode({"access_key": self.api_key, "search": search, "limit": 5})
        return json_request(method="GET", url=f"{self.base_url}/airports?{query}")

    def flights(
        self,
        *,
        flight_date: str,
        dep_iata: str,
        arr_iata: str,
    ) -> Dict[str, Any]:
        query = urlencode(
            {
                "access_key": self.api_key,
                "flight_date": flight_date,
                "dep_iata": dep_iata,
                "arr_iata": arr_iata,
                "limit": 5,
            }
        )
        return json_request(method="GET", url=f"{self.base_url}/flights?{query}")
