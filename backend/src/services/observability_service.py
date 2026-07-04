from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging import Logger

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.application.audit.mappers import audit_event_response_from_record
from src.application.observability.schemas import (
    AlertResponse,
    AlertsResponse,
    DecisionTimelineItemResponse,
    ObservabilityMetricsResponse,
    ProviderMetricsResponse,
    RunMetricsResponse,
    RunTraceResponse,
    WorkflowStepMetricsResponse,
)
from src.application.workflows.mappers import workflow_run_response_from_record
from src.application.workflows.step_mappers import workflow_run_step_response_from_record
from src.core.config import Settings
from src.db.models import AuditEventModel, WorkflowRunModel, WorkflowRunStepModel
from src.domain.audit.models import AuditEvent
from src.domain.audit.repositories import AuditEventRepository
from src.domain.workflows.models import WorkflowRunStatus
from src.domain.workflows.repositories import WorkflowRunRepository
from src.domain.workflows.step_repositories import WorkflowRunStepRepository


@dataclass
class ProviderAggregate:
    calls: int = 0
    failures: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0


class ObservabilityService:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session],
        workflow_run_repository: WorkflowRunRepository,
        workflow_run_step_repository: WorkflowRunStepRepository,
        audit_repository: AuditEventRepository,
        logger: Logger,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.workflow_run_repository = workflow_run_repository
        self.workflow_run_step_repository = workflow_run_step_repository
        self.audit_repository = audit_repository
        self.logger = logger

    def metrics_report(self, *, lookback_hours: int | None = None) -> ObservabilityMetricsResponse:
        resolved_lookback = lookback_hours or self.settings.observability.metrics_lookback_hours
        since = datetime.utcnow() - timedelta(hours=resolved_lookback)

        with self.session_factory() as session:
            runs = list(
                session.execute(
                    select(WorkflowRunModel).where(WorkflowRunModel.created_at >= since).order_by(WorkflowRunModel.created_at)
                ).scalars()
            )
            steps = list(
                session.execute(
                    select(WorkflowRunStepModel).where(WorkflowRunStepModel.started_at >= since).order_by(WorkflowRunStepModel.started_at)
                ).scalars()
            )
            audit_events = list(
                session.execute(
                    select(AuditEventModel).where(AuditEventModel.occurred_at >= since).order_by(AuditEventModel.occurred_at)
                ).scalars()
            )

        terminal_runs = [
            run
            for run in runs
            if run.status
            in {
                WorkflowRunStatus.SUCCEEDED.value,
                WorkflowRunStatus.FAILED.value,
                WorkflowRunStatus.CANCELLED.value,
                WorkflowRunStatus.DEAD_LETTERED.value,
            }
        ]
        total_runs = len(runs)
        succeeded_runs = sum(1 for run in runs if run.status == WorkflowRunStatus.SUCCEEDED.value)
        failed_runs = sum(1 for run in runs if run.status == WorkflowRunStatus.FAILED.value)
        cancelled_runs = sum(1 for run in runs if run.status == WorkflowRunStatus.CANCELLED.value)
        dead_lettered_runs = sum(1 for run in runs if run.status == WorkflowRunStatus.DEAD_LETTERED.value)
        queued_or_running_runs = sum(
            1 for run in runs if run.status in {WorkflowRunStatus.QUEUED.value, WorkflowRunStatus.RUNNING.value}
        )
        retry_count_total = sum(int(run.retry_count or 0) for run in runs)
        success_rate = round(succeeded_runs / total_runs, 4) if total_runs else 0.0
        failure_rate = round((failed_runs + dead_lettered_runs) / total_runs, 4) if total_runs else 0.0
        average_terminal_duration_seconds = round(
            sum((run.updated_at - run.created_at).total_seconds() for run in terminal_runs) / len(terminal_runs), 2
        ) if terminal_runs else 0.0

        step_groups: dict[str, list[WorkflowRunStepModel]] = defaultdict(list)
        for step in steps:
            step_groups[step.step_name].append(step)
        step_metrics = [
            WorkflowStepMetricsResponse(
                step_name=step_name,
                executions=len(group),
                failures=sum(1 for item in group if item.status != "succeeded"),
                avg_latency_ms=round(
                    sum(
                        ((item.completed_at or item.started_at) - item.started_at).total_seconds() * 1000
                        for item in group
                    )
                    / len(group),
                    2,
                ) if group else 0.0,
            )
            for step_name, group in sorted(step_groups.items())
        ]

        provider_aggregates: dict[tuple[str, str | None], ProviderAggregate] = defaultdict(ProviderAggregate)
        token_usage_total = 0
        cost_usd_total = 0.0
        for record in audit_events:
            payload = self._decode_json(record.payload_json)
            if record.event_type == "tool_called":
                provider_key = (record.provider_name or "unknown", record.provider_endpoint)
                aggregate = provider_aggregates[provider_key]
                aggregate.calls += 1
                aggregate.total_tokens += int(payload.get("total_tokens", 0) or 0)
                aggregate.total_cost_usd += float(payload.get("estimated_cost_usd", 0.0) or 0.0)
                aggregate.total_latency_ms += float(payload.get("latency_ms", 0.0) or 0.0)
                token_usage_total += int(payload.get("total_tokens", 0) or 0)
                cost_usd_total += float(payload.get("estimated_cost_usd", 0.0) or 0.0)
            elif record.event_type == "tool_failed":
                provider_key = (record.provider_name or "unknown", record.provider_endpoint)
                aggregate = provider_aggregates[provider_key]
                aggregate.failures += 1

        provider_metrics = [
            ProviderMetricsResponse(
                provider_name=provider_name,
                provider_endpoint=provider_endpoint,
                calls=aggregate.calls,
                failures=aggregate.failures,
                total_tokens=aggregate.total_tokens,
                total_cost_usd=round(aggregate.total_cost_usd, 8),
                avg_latency_ms=round(aggregate.total_latency_ms / aggregate.calls, 2) if aggregate.calls else 0.0,
            )
            for (provider_name, provider_endpoint), aggregate in sorted(provider_aggregates.items())
        ]

        return ObservabilityMetricsResponse(
            lookback_hours=resolved_lookback,
            generated_at=datetime.utcnow(),
            runs=RunMetricsResponse(
                total_runs=total_runs,
                succeeded_runs=succeeded_runs,
                failed_runs=failed_runs,
                cancelled_runs=cancelled_runs,
                dead_lettered_runs=dead_lettered_runs,
                success_rate=success_rate,
                failure_rate=failure_rate,
                average_terminal_duration_seconds=average_terminal_duration_seconds,
                queued_or_running_runs=queued_or_running_runs,
                retry_count_total=retry_count_total,
            ),
            step_metrics=step_metrics,
            provider_metrics=provider_metrics,
            token_usage_total=token_usage_total,
            cost_usd_total=round(cost_usd_total, 8),
        )

    def alerts_report(self, *, lookback_hours: int | None = None) -> AlertsResponse:
        metrics = self.metrics_report(lookback_hours=lookback_hours)
        alerts: list[AlertResponse] = []

        if metrics.runs.failure_rate > self.settings.observability.failure_rate_alert_threshold:
            alerts.append(
                AlertResponse(
                    code="run_failure_rate_high",
                    severity="high",
                    summary="Workflow run failure rate exceeded threshold.",
                    details={
                        "failure_rate": metrics.runs.failure_rate,
                        "threshold": self.settings.observability.failure_rate_alert_threshold,
                    },
                )
            )

        if metrics.runs.dead_lettered_runs >= self.settings.observability.dead_letter_alert_threshold:
            alerts.append(
                AlertResponse(
                    code="dead_letter_runs_present",
                    severity="high",
                    summary="Dead-lettered workflow runs were detected.",
                    details={"dead_lettered_runs": metrics.runs.dead_lettered_runs},
                )
            )

        provider_failure_total = sum(item.failures for item in metrics.provider_metrics)
        if provider_failure_total >= self.settings.observability.provider_failure_alert_threshold:
            alerts.append(
                AlertResponse(
                    code="provider_failures_high",
                    severity="medium",
                    summary="Provider failure volume exceeded threshold.",
                    details={
                        "provider_failures": provider_failure_total,
                        "threshold": self.settings.observability.provider_failure_alert_threshold,
                    },
                )
            )

        stuck_runs = self._find_stuck_runs()
        if stuck_runs:
            alerts.append(
                AlertResponse(
                    code="stuck_runs_detected",
                    severity="high",
                    summary="Queued or running workflow runs have exceeded the stuck threshold.",
                    details={"run_ids": stuck_runs},
                )
            )

        for alert in alerts:
            self.logger.warning(
                "observability.alert",
                extra={
                    "alert_code": alert.code,
                    "severity": alert.severity,
                    "status": "active",
                },
            )

        return AlertsResponse(generated_at=datetime.utcnow(), healthy=not alerts, alerts=alerts)

    def run_trace(self, *, run_id: str) -> RunTraceResponse | None:
        run = self.workflow_run_repository.get(run_id)
        if run is None:
            return None
        steps = self.workflow_run_step_repository.list_by_run_id(run_id)
        audit_events = self.audit_repository.list_by_run_id(run_id)
        return RunTraceResponse(
            run=workflow_run_response_from_record(run),
            steps=[workflow_run_step_response_from_record(item) for item in steps],
            audit_events=[audit_event_response_from_record(item) for item in audit_events],
            decision_timeline=self._build_decision_timeline(audit_events),
        )

    def _build_decision_timeline(self, audit_events) -> list[DecisionTimelineItemResponse]:
        timeline: list[DecisionTimelineItemResponse] = []
        for record in audit_events:
            item = self._translate_audit_event(record)
            if item is not None:
                timeline.append(item)
        return timeline

    def _translate_audit_event(self, record: AuditEvent) -> DecisionTimelineItemResponse | None:
        payload = record.payload
        event_type = record.event_type
        actor = self._humanize_actor(record.node_name or event_type)

        if event_type == "coordinator_decision":
            next_roles = [self._humanize_actor(role) for role in payload.get("next_roles", [])]
            if next_roles:
                headline = f"Coordinator routed work to {self._format_list(next_roles)}"
            else:
                headline = "Coordinator stopped autonomous routing"
            detail = str(payload.get("rationale") or payload.get("summary") or "The coordinator evaluated the latest artifacts.")
            if payload.get("waiting_for_user"):
                detail = f"{detail} The workflow is waiting for user clarification before it can continue."
            return DecisionTimelineItemResponse(
                occurred_at=record.occurred_at,
                kind="coordination",
                actor="Coordinator",
                headline=headline,
                detail=detail,
            )

        if event_type == "parallel_batch_started":
            roles = [self._humanize_actor(role) for role in payload.get("roles", [])]
            return DecisionTimelineItemResponse(
                occurred_at=record.occurred_at,
                kind="coordination",
                actor="Coordinator",
                headline=f"Parallel work started for {self._format_list(roles)}" if roles else "Parallel work started",
                detail=str(payload.get("summary") or "Independent specialists were released together to reduce latency."),
            )

        if event_type == "parallel_batch_completed":
            roles = [self._humanize_actor(role) for role in payload.get("roles", [])]
            return DecisionTimelineItemResponse(
                occurred_at=record.occurred_at,
                kind="coordination",
                actor="Coordinator",
                headline=f"Parallel work finished for {self._format_list(roles)}" if roles else "Parallel work finished",
                detail=str(payload.get("summary") or "The parallel specialist batch completed and results were merged."),
            )

        if event_type == "specialist_started":
            return DecisionTimelineItemResponse(
                occurred_at=record.occurred_at,
                kind="execution",
                actor=actor,
                headline=f"{actor} started",
                detail=str(payload.get("summary") or "The specialist began working on its assigned task."),
            )

        if event_type == "specialist_completed":
            return DecisionTimelineItemResponse(
                occurred_at=record.occurred_at,
                kind="decision",
                actor=actor,
                headline=f"{actor} finished",
                detail=str(payload.get("summary") or "The specialist produced an output for the workflow."),
                confidence=self._coerce_confidence(payload.get("confidence")),
            )

        if event_type == "workflow_terminal_decision":
            return DecisionTimelineItemResponse(
                occurred_at=record.occurred_at,
                kind="terminal",
                actor="Coordinator",
                headline="Workflow reached a terminal decision",
                detail=str(payload.get("terminal_reason") or "The workflow ended after the coordinator determined no further actions were needed."),
            )

        if event_type == "tool_called":
            if record.tool_name == "json_completion":
                return None
            evidence = [value for value in [record.provider_name, record.tool_name] if value]
            return DecisionTimelineItemResponse(
                occurred_at=record.occurred_at,
                kind="evidence",
                actor=actor,
                headline=f"{actor} checked {self._tool_label(record.tool_name)}",
                detail=self._tool_success_detail(record, payload),
                evidence=evidence,
            )

        if event_type == "tool_failed":
            if record.tool_name == "json_completion":
                return None
            evidence = [value for value in [record.provider_name, record.tool_name] if value]
            return DecisionTimelineItemResponse(
                occurred_at=record.occurred_at,
                kind="warning",
                actor=actor,
                headline=f"{actor} could not use {self._tool_label(record.tool_name)}",
                detail=self._tool_failure_detail(record, payload),
                evidence=evidence,
            )

        return None

    def _humanize_actor(self, value: str) -> str:
        aliases = {
            "coordinator_agent": "Coordinator",
            "clarification": "Clarification",
            "destination_research": "Destination Research",
            "itinerary": "Itinerary",
            "stay": "Stay",
            "transport": "Transport",
            "food": "Food",
            "budget": "Budget",
            "safety": "Safety",
            "review": "Review",
            "governance": "Governance",
            "clarification_validator": "Clarification Check",
            "research_signal_agent": "Planning Signals",
            "destination_research_agent": "Destination Research",
            "itinerary_planning_agent": "Itinerary Planning",
            "stay_recommendation_agent": "Stay Recommendations",
            "local_transport_agent": "Local Transport",
            "food_recommendation_agent": "Food Recommendations",
            "budget_optimization_agent": "Budget Review",
            "solo_women_safety_advisor_agent": "Safety Review",
            "review_and_consistency_agent": "Consistency Review",
            "governance_gate_agent": "Governance Check",
            "parallel_batch": "Parallel Batch",
        }
        return aliases.get(value, value.replace("_", " ").title())

    def _tool_label(self, tool_name: str | None) -> str:
        if not tool_name:
            return "an external source"
        return tool_name.replace("_", " ")

    def _tool_success_detail(self, record: AuditEvent, payload: dict[str, object]) -> str:
        provider = record.provider_name or "an external provider"
        latency = payload.get("latency_ms")
        details = f"{provider} returned supporting evidence for this step."
        if latency is not None:
            details = f"{details} Response time was about {round(float(latency), 1)} ms."
        return details

    def _tool_failure_detail(self, record: AuditEvent, payload: dict[str, object]) -> str:
        provider = record.provider_name or "an external provider"
        status = record.status or "failed"
        latency = payload.get("latency_ms")
        details = f"{provider} did not return usable evidence ({status}). The workflow used fallback logic where possible."
        if latency is not None:
            details = f"{details} The failed call took about {round(float(latency), 1)} ms."
        return details

    def _coerce_confidence(self, value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_list(self, items: list[str]) -> str:
        cleaned = [item for item in items if item]
        if not cleaned:
            return "no specialists"
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} and {cleaned[1]}"
        return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"

    def _find_stuck_runs(self) -> list[str]:
        threshold = datetime.utcnow() - timedelta(minutes=self.settings.observability.stuck_run_threshold_minutes)
        with self.session_factory() as session:
            stuck_runs = list(
                session.execute(
                    select(WorkflowRunModel.run_id).where(
                        WorkflowRunModel.status.in_(
                            [WorkflowRunStatus.QUEUED.value, WorkflowRunStatus.RUNNING.value]
                        ),
                        WorkflowRunModel.updated_at < threshold,
                    )
                ).scalars()
            )
        return stuck_runs

    @staticmethod
    def _decode_json(raw: str | None) -> dict[str, object]:
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
