from __future__ import annotations

from src.agents.travel_planner.tooling.base import (
    JsonCompletionInput,
    ToolAuthMethod,
    ToolMetadata,
    ToolSideEffectLevel,
    ToolUnavailableError,
    ToolUsage,
)
from src.agents.travel_planner.tooling.contracts import JsonCompletionOutput
from src.providers.llm import OpenAIChatClient


class OpenAIJsonCompletionTool:
    name = "json_completion"
    metadata = ToolMetadata(
        name="json_completion",
        description="Runs a structured JSON completion against the configured LLM.",
        allowed_agents=(
            "destination_research_agent",
            "itinerary_planning_agent",
            "stay_recommendation_agent",
            "local_transport_agent",
            "food_recommendation_agent",
            "budget_optimization_agent",
            "solo_women_safety_advisor_agent",
            "review_and_consistency_agent",
        ),
        provider_name="openai",
        provider_endpoint="responses",
        auth_method=ToolAuthMethod.API_KEY,
        timeout_seconds=30,
        retry_policy="retry_once",
        rate_limit_per_minute=60,
        side_effect_level=ToolSideEffectLevel.EXTERNAL_READ,
        input_model=JsonCompletionInput,
        output_model=JsonCompletionOutput,
    )

    def __init__(self, client: OpenAIChatClient | None) -> None:
        self.client = client

    def is_available(self) -> bool:
        return self.client is not None

    def execute(self, payload: JsonCompletionInput) -> JsonCompletionOutput:
        if self.client is None:
            raise ToolUnavailableError("OpenAI API key is not configured.")
        completion = self.client.json_completion(
            developer_prompt=payload.developer_prompt,
            user_prompt=payload.user_prompt,
        )
        return JsonCompletionOutput(
            payload=completion["payload"],
            usage=ToolUsage(
                prompt_tokens=completion["usage"].get("prompt_tokens", 0),
                completion_tokens=completion["usage"].get("completion_tokens", 0),
                total_tokens=completion["usage"].get("total_tokens", 0),
                estimated_cost_usd=completion["usage"].get("estimated_cost_usd", 0.0),
            ),
        )
