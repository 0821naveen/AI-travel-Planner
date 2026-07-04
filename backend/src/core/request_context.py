from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None


_request_context: ContextVar[Optional[RequestContext]] = ContextVar("request_context", default=None)


def set_request_context(context: RequestContext) -> object:
    return _request_context.set(context)


def get_request_context() -> Optional[RequestContext]:
    return _request_context.get()


def reset_request_context(token: object) -> None:
    _request_context.reset(token)
