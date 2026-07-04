from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generic, Protocol, Type, TypeVar

from pydantic import BaseModel, Field

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ToolUnavailableError(RuntimeError):
    pass


class ToolAuthorizationError(RuntimeError):
    pass


class ToolInputValidationError(RuntimeError):
    pass


class ToolOutputValidationError(RuntimeError):
    pass


class ToolAuthMethod(str, Enum):
    NONE = "none"
    API_KEY = "api_key"


class ToolSideEffectLevel(str, Enum):
    READ_ONLY = "read_only"
    EXTERNAL_READ = "external_read"
    WRITE = "write"


class ToolUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class ToolOutputBase(BaseModel):
    usage: ToolUsage = Field(default_factory=ToolUsage)


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    description: str
    allowed_agents: tuple[str, ...]
    provider_name: str
    provider_endpoint: str
    auth_method: ToolAuthMethod
    timeout_seconds: int
    retry_policy: str
    rate_limit_per_minute: int
    side_effect_level: ToolSideEffectLevel
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]


class ToolAuditEntry(BaseModel):
    tool_name: str
    agent_name: str
    run_id: str
    status: str
    latency_ms: float
    provider_name: str
    provider_endpoint: str
    auth_method: ToolAuthMethod
    retry_policy: str
    rate_limit_per_minute: int
    side_effect_level: ToolSideEffectLevel
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PlannerTool(Protocol, Generic[InputT, OutputT]):
    name: str
    metadata: ToolMetadata

    def is_available(self) -> bool: ...

    def execute(self, payload: InputT) -> OutputT: ...


class JsonCompletionInput(BaseModel):
    developer_prompt: str
    user_prompt: str
