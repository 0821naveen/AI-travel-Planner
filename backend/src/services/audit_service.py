from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from src.core.redaction import redact_payload
from src.domain.audit.models import AuditEvent
from src.domain.audit.repositories import AuditEventRepository


class AuditService:
    def __init__(self, *, repository: AuditEventRepository) -> None:
        self.repository = repository

    def record_event(
        self,
        *,
        event_type: str,
        request_id: str | None = None,
        trip_id: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        status: str | None = None,
        node_name: str | None = None,
        tool_name: str | None = None,
        provider_name: str | None = None,
        provider_endpoint: str | None = None,
        model_name: str | None = None,
        prompt_version: str | None = None,
        source_references: list[str] | None = None,
        payload: dict[str, object] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            occurred_at=datetime.utcnow(),
            request_id=request_id,
            trip_id=trip_id,
            run_id=run_id,
            job_id=job_id,
            actor_id=actor_id,
            actor_role=actor_role,
            status=status,
            node_name=node_name,
            tool_name=tool_name,
            provider_name=provider_name,
            provider_endpoint=provider_endpoint,
            model_name=model_name,
            prompt_version=prompt_version,
            source_references=list(source_references or []),
            payload=redact_payload(payload or {}),
        )
        return self.repository.append(event)

    def list_by_run_id(self, run_id: str) -> list[AuditEvent]:
        return self.repository.list_by_run_id(run_id)
