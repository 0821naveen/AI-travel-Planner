from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from src.core.config import Settings


class DefaultFieldFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for field in (
            "request_id",
            "trip_id",
            "run_id",
            "job_id",
            "actor_id",
            "actor_role",
            "node_name",
            "tool_name",
            "provider_name",
            "provider_endpoint",
            "latency_ms",
            "retry_count",
            "status",
            "alert_code",
            "severity",
        ):
            if not hasattr(record, field):
                setattr(record, field, None)
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "trip_id": getattr(record, "trip_id", None),
            "run_id": getattr(record, "run_id", None),
            "job_id": getattr(record, "job_id", None),
            "actor_id": getattr(record, "actor_id", None),
            "actor_role": getattr(record, "actor_role", None),
            "node_name": getattr(record, "node_name", None),
            "tool_name": getattr(record, "tool_name", None),
            "provider_name": getattr(record, "provider_name", None),
            "provider_endpoint": getattr(record, "provider_endpoint", None),
            "latency_ms": getattr(record, "latency_ms", None),
            "retry_count": getattr(record, "retry_count", None),
            "status": getattr(record, "status", None),
            "alert_code": getattr(record, "alert_code", None),
            "severity": getattr(record, "severity", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings, level: Optional[int] = None) -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    resolved_level = level if level is not None else getattr(logging, settings.logging.level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(DefaultFieldFilter())
    handler.setFormatter(JsonLogFormatter())

    root_logger.setLevel(resolved_level)
    root_logger.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or "travel_planner")
