from __future__ import annotations

from datetime import date

from src.providers import (
    AviationstackClient,
    OpenAIChatClient,
    ResearchClientError,
    SerpApiClient,
    TavilyClient,
    WeatherApiClient,
    build_clients,
)


def days_until(target_date: date, today: date) -> int:
    return (target_date - today).days


__all__ = [
    "AviationstackClient",
    "OpenAIChatClient",
    "ResearchClientError",
    "SerpApiClient",
    "TavilyClient",
    "WeatherApiClient",
    "build_clients",
    "days_until",
]
