from __future__ import annotations

from typing import Optional, Tuple

from src.core.config import get_settings
from src.providers.llm import OpenAIChatClient
from src.providers.search import SerpApiClient, TavilyClient
from src.providers.travel import AviationstackClient, WeatherApiClient


def build_clients() -> Tuple[
    Optional[TavilyClient],
    Optional[WeatherApiClient],
    Optional[OpenAIChatClient],
    Optional[SerpApiClient],
    Optional[AviationstackClient],
]:
    settings = get_settings()
    tavily_client = TavilyClient(settings.tavily_api_key) if settings.tavily_api_key else None
    weather_client = WeatherApiClient(settings.weatherapi_api_key) if settings.weatherapi_api_key else None
    openai_client = (
        OpenAIChatClient(api_key=settings.openai_api_key, model=settings.openai_model)
        if settings.openai_api_key
        else None
    )
    serpapi_client = SerpApiClient(settings.serpapi_api_key) if settings.serpapi_api_key else None
    aviationstack_client = AviationstackClient(settings.aviationstack_api_key) if settings.aviationstack_api_key else None
    return tavily_client, weather_client, openai_client, serpapi_client, aviationstack_client
