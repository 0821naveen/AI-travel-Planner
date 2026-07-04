from __future__ import annotations

from src.agents.travel_planner.tooling.llm_tools import OpenAIJsonCompletionTool
from src.agents.travel_planner.tooling.registry import ToolExecutor, ToolRegistry
from src.agents.travel_planner.tooling.search_tools import (
    SerpApiGoogleFlightsTool,
    SerpApiTripadvisorTool,
    TavilyWebSearchTool,
)
from src.agents.travel_planner.tooling.travel_tools import (
    AviationstackFlightScheduleTool,
    SerpApiGoogleHotelsTool,
    SerpApiYouTubeVideoTool,
    WeatherLookupTool,
)
from src.providers import build_clients


def build_tool_registry() -> ToolRegistry:
    tavily_client, weather_client, openai_client, serpapi_client, aviationstack_client = build_clients()
    return ToolRegistry(
        tools=[
            TavilyWebSearchTool(tavily_client),
            WeatherLookupTool(weather_client),
            OpenAIJsonCompletionTool(openai_client),
            SerpApiGoogleHotelsTool(serpapi_client),
            SerpApiYouTubeVideoTool(serpapi_client),
            SerpApiTripadvisorTool(serpapi_client),
            SerpApiGoogleFlightsTool(serpapi_client),
            AviationstackFlightScheduleTool(aviationstack_client),
        ]
    )


def build_tool_executor(context, agent_name: str) -> ToolExecutor:
    return ToolExecutor(build_tool_registry(), context=context, agent_name=agent_name)
