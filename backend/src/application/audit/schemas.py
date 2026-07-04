from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    event_id: str
    event_type: str
    occurred_at: datetime
    request_id: Optional[str] = None
    trip_id: Optional[str] = None
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    status: Optional[str] = None
    node_name: Optional[str] = None
    tool_name: Optional[str] = None
    provider_name: Optional[str] = None
    provider_endpoint: Optional[str] = None
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    source_references: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
