from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = {
    "api_key",
    "api_keys",
    "authorization",
    "password",
    "secret",
    "token",
    "notes",
}

EMAIL_PATTERN = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_PATTERN = re.compile(r"\+?\d[\d\-\s]{7,}\d")


def redact_text(value: str) -> str:
    value = EMAIL_PATTERN.sub("[redacted-email]", value)
    value = PHONE_PATTERN.sub("[redacted-phone]", value)
    return value


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
