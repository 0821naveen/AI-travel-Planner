from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Deque, Dict, Optional, Protocol

from fastapi import Depends, HTTPException, Request, status

from src.core.config import Settings, get_settings
from src.services.auth_service import AuthService


class ActorRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"


@dataclass(frozen=True)
class ActorContext:
    actor_id: Optional[str]
    role: ActorRole


class RateLimiter(Protocol):
    def check(self, key: str) -> None: ...


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = limit_per_minute
        self._history: Dict[str, Deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            history = self._history.setdefault(key, deque())
            while history and now - history[0] > 60:
                history.popleft()
            if len(history) >= self.limit_per_minute:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
            history.append(now)


class RedisRateLimiter:
    def __init__(self, redis_client, limit_per_minute: int) -> None:
        self.redis_client = redis_client
        self.limit_per_minute = limit_per_minute

    def check(self, key: str) -> None:
        bucket = f"rate-limit:{key}:{int(time.time() // 60)}"
        try:
            count = int(self.redis_client.incr(bucket))
            if count == 1:
                self.redis_client.expire(bucket, 61)
            if count > self.limit_per_minute:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        except HTTPException:
            raise
        except Exception:
            return


def resolve_client_key(request: Request, settings: Settings) -> str:
    client_host = request.client.host if request.client else "unknown"
    if settings.security.trusted_proxy_headers and client_host in settings.security.trusted_proxy_ips:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return client_host


def validate_api_key(request: Request, settings: Settings) -> None:
    if not settings.security.enabled:
        return
    if request.url.path.endswith("/health") and settings.security.allow_healthcheck_without_auth:
        return

    header_name = settings.security.api_key_header
    provided = request.headers.get(header_name)
    if not provided or provided not in settings.security.api_keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def extract_actor(request: Request, settings: Settings) -> ActorContext:
    auth_header = request.headers.get(settings.auth.token_header, "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        auth_service: AuthService | None = getattr(getattr(request.app.state, "container", None), "auth_service", None)
        if auth_service is not None and token:
            payload = auth_service.decode_token(token)
            actor_id = payload.get("sub")
            role_value = payload.get("role", ActorRole.USER.value)
            if isinstance(actor_id, str) and isinstance(role_value, str):
                try:
                    return ActorContext(actor_id=actor_id, role=ActorRole(role_value))
                except ValueError as exc:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid actor role") from exc

    actor_id = request.headers.get(settings.security.actor_id_header)
    raw_role = request.headers.get(settings.security.actor_role_header, ActorRole.USER.value).lower()
    try:
        role = ActorRole(raw_role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid actor role") from exc
    return ActorContext(actor_id=actor_id, role=role)


def require_roles(*roles: ActorRole):
    def _dependency(request: Request, settings: Settings = Depends(get_settings)) -> ActorContext:
        actor = extract_actor(request, settings)
        if settings.security.enabled and actor.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return actor

    return _dependency


def build_rate_limiter(settings: Settings) -> RateLimiter:
    try:
        from redis import Redis
    except Exception:
        return InMemoryRateLimiter(limit_per_minute=settings.security.rate_limit_per_minute)

    client = Redis.from_url(settings.redis.url, decode_responses=True)
    return RedisRateLimiter(client, limit_per_minute=settings.security.rate_limit_per_minute)
