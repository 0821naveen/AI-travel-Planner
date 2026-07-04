from __future__ import annotations

from typing import Protocol

from src.domain.audit.models import AuditEvent


class AuditEventRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...

    def list_by_run_id(self, run_id: str) -> list[AuditEvent]: ...
