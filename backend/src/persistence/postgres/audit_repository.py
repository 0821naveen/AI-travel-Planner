from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import AuditEventModel
from src.domain.audit.models import AuditEvent
from src.domain.audit.repositories import AuditEventRepository


class PostgresAuditEventRepository(AuditEventRepository):
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def append(self, event: AuditEvent) -> AuditEvent:
        with self.session_factory() as session:
            record = AuditEventModel(
                event_id=event.event_id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                request_id=event.request_id,
                trip_id=event.trip_id,
                run_id=event.run_id,
                job_id=event.job_id,
                actor_id=event.actor_id,
                actor_role=event.actor_role,
                status=event.status,
                node_name=event.node_name,
                tool_name=event.tool_name,
                provider_name=event.provider_name,
                provider_endpoint=event.provider_endpoint,
                model_name=event.model_name,
                prompt_version=event.prompt_version,
                source_references_json=json.dumps(event.source_references),
                payload_json=json.dumps(event.payload),
            )
            session.add(record)
            session.commit()
        return event

    def list_by_run_id(self, run_id: str) -> list[AuditEvent]:
        with self.session_factory() as session:
            statement = select(AuditEventModel).where(AuditEventModel.run_id == run_id).order_by(AuditEventModel.occurred_at)
            return [self._to_domain(record) for record in session.execute(statement).scalars()]

    @staticmethod
    def _to_domain(record: AuditEventModel) -> AuditEvent:
        return AuditEvent(
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
            source_references=json.loads(record.source_references_json or "[]"),
            payload=json.loads(record.payload_json or "{}"),
        )
