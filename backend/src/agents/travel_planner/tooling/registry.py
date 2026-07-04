from __future__ import annotations

import time
from typing import Any, Iterable

from pydantic import ValidationError

from src.agents.travel_planner.state import PlannerContext
from src.agents.travel_planner.tooling.base import (
    PlannerTool,
    ToolAuditEntry,
    ToolAuthorizationError,
    ToolInputValidationError,
    ToolOutputValidationError,
    ToolUnavailableError,
)


class ToolRegistry:
    def __init__(self, tools: Iterable[PlannerTool[Any, Any]]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> PlannerTool[Any, Any]:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool '{name}'") from exc

    def is_available(self, name: str) -> bool:
        return self.get(name).is_available()

    def metadata(self, name: str):
        return self.get(name).metadata


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, *, context: PlannerContext, agent_name: str) -> None:
        self.registry = registry
        self.context = context
        self.agent_name = agent_name

    def execute(self, name: str, payload: Any) -> Any:
        tool = self.registry.get(name)
        metadata = tool.metadata
        if not tool.is_available():
            raise ToolUnavailableError(f"Tool '{name}' is unavailable")
        if self.agent_name not in metadata.allowed_agents:
            raise ToolAuthorizationError(f"Agent '{self.agent_name}' is not allowed to use tool '{name}'")

        try:
            validated_input = metadata.input_model.model_validate(payload)
        except ValidationError as exc:
            self.context.append_audit_event(
                {
                    "event_type": "tool_failed",
                    "run_id": self.context.run_id,
                    "trip_id": self.context.trip_id,
                    "node_name": self.agent_name,
                    "tool_name": name,
                    "provider_name": metadata.provider_name,
                    "provider_endpoint": metadata.provider_endpoint,
                    "status": "invalid_input",
                }
            )
            raise ToolInputValidationError(f"Invalid input for tool '{name}'") from exc

        started = time.perf_counter()
        try:
            raw_output = tool.execute(validated_input)
        except Exception:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            self.context.append_audit_event(
                {
                    "event_type": "tool_failed",
                    "run_id": self.context.run_id,
                    "trip_id": self.context.trip_id,
                    "node_name": self.agent_name,
                    "tool_name": name,
                    "provider_name": metadata.provider_name,
                    "provider_endpoint": metadata.provider_endpoint,
                    "status": "execution_failed",
                    "latency_ms": latency_ms,
                }
            )
            raise
        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        try:
            validated_output = metadata.output_model.model_validate(raw_output)
        except ValidationError as exc:
            self.context.append_audit_event(
                {
                    "event_type": "tool_failed",
                    "run_id": self.context.run_id,
                    "trip_id": self.context.trip_id,
                    "node_name": self.agent_name,
                    "tool_name": name,
                    "provider_name": metadata.provider_name,
                    "provider_endpoint": metadata.provider_endpoint,
                    "status": "invalid_output",
                    "latency_ms": latency_ms,
                }
            )
            raise ToolOutputValidationError(f"Invalid output from tool '{name}'") from exc

        usage = getattr(validated_output, "usage", None)
        total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
        estimated_cost = getattr(usage, "estimated_cost_usd", 0.0) if usage else 0.0
        budget = self.context.short_term_memory.setdefault(
            "tool_budget",
            {"total_tokens": 0, "total_cost_usd": 0.0, "total_latency_ms": 0.0, "tool_calls": 0},
        )
        if isinstance(budget, dict):
            budget["total_tokens"] = int(budget.get("total_tokens", 0)) + int(total_tokens)
            budget["total_cost_usd"] = float(budget.get("total_cost_usd", 0.0)) + float(estimated_cost)
            budget["total_latency_ms"] = float(budget.get("total_latency_ms", 0.0)) + float(latency_ms)
            budget["tool_calls"] = int(budget.get("tool_calls", 0)) + 1

        self.context.append_tool_audit(
            ToolAuditEntry(
                tool_name=name,
                agent_name=self.agent_name,
                run_id=self.context.run_id or self.context.trip_id,
                status="success",
                latency_ms=latency_ms,
                provider_name=metadata.provider_name,
                provider_endpoint=metadata.provider_endpoint,
                auth_method=metadata.auth_method,
                retry_policy=metadata.retry_policy,
                rate_limit_per_minute=metadata.rate_limit_per_minute,
                side_effect_level=metadata.side_effect_level,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
            ).model_dump(mode="json")
        )
        self.context.append_audit_event(
            {
                "event_type": "tool_called",
                "run_id": self.context.run_id,
                "trip_id": self.context.trip_id,
                "node_name": self.agent_name,
                "tool_name": name,
                "provider_name": metadata.provider_name,
                "provider_endpoint": metadata.provider_endpoint,
                "status": "success",
                "latency_ms": latency_ms,
                "total_tokens": total_tokens,
                "estimated_cost_usd": estimated_cost,
            }
        )
        return validated_output
