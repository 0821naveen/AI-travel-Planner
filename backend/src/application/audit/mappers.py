from __future__ import annotations

from src.application.audit.schemas import AuditEventResponse
from src.domain.audit.models import AuditEvent


def audit_event_response_from_record(record: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        event_id=record.event_id,
        event_type=record.event_type,
        occurred_at=record.occurred_at,
        request_id=record.request_id,
        trip_id=record.trip_id,
        run_id=record.run_id,
        job_id=record.job_id,
        actor_id=record.actor_id,
        actor_role=record.actor_role,
        status=record.status,
        node_name=record.node_name,
        tool_name=record.tool_name,
        provider_name=record.provider_name,
        provider_endpoint=record.provider_endpoint,
        model_name=record.model_name,
        prompt_version=record.prompt_version,
        source_references=record.source_references,
        payload=record.payload,
    )
