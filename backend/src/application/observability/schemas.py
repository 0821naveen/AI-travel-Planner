from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.application.audit.schemas import AuditEventResponse
from src.application.workflows.schemas import WorkflowRunResponse
from src.application.workflows.step_schemas import WorkflowRunStepResponse


class ProviderMetricsResponse(BaseModel):
    provider_name: str
    provider_endpoint: Optional[str] = None
    calls: int = 0
    failures: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0


class WorkflowStepMetricsResponse(BaseModel):
    step_name: str
    executions: int = 0
    failures: int = 0
    avg_latency_ms: float = 0.0


class RunMetricsResponse(BaseModel):
    total_runs: int = 0
    succeeded_runs: int = 0
    failed_runs: int = 0
    cancelled_runs: int = 0
    dead_lettered_runs: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    average_terminal_duration_seconds: float = 0.0
    queued_or_running_runs: int = 0
    retry_count_total: int = 0


class ObservabilityMetricsResponse(BaseModel):
    lookback_hours: int
    generated_at: datetime
    runs: RunMetricsResponse
    step_metrics: list[WorkflowStepMetricsResponse] = Field(default_factory=list)
    provider_metrics: list[ProviderMetricsResponse] = Field(default_factory=list)
    token_usage_total: int = 0
    cost_usd_total: float = 0.0


class AlertResponse(BaseModel):
    code: str
    severity: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class AlertsResponse(BaseModel):
    generated_at: datetime
    healthy: bool
    alerts: list[AlertResponse] = Field(default_factory=list)


class DecisionTimelineItemResponse(BaseModel):
    occurred_at: datetime
    kind: str
    actor: str
    headline: str
    detail: str
    confidence: Optional[float] = None
    evidence: list[str] = Field(default_factory=list)


class RunTraceResponse(BaseModel):
    run: WorkflowRunResponse
    steps: list[WorkflowRunStepResponse] = Field(default_factory=list)
    audit_events: list[AuditEventResponse] = Field(default_factory=list)
    decision_timeline: list[DecisionTimelineItemResponse] = Field(default_factory=list)
