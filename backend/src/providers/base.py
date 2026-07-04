from __future__ import annotations

import json
from socket import timeout as SocketTimeout
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.core.config import get_settings


class ResearchClientError(RuntimeError):
    pass


def json_request(
    *,
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    body = None
    request_headers = dict(headers or {})

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(url=url, data=body, method=method, headers=request_headers)

    try:
        with urlopen(request, timeout=settings.provider_runtime.request_timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise ResearchClientError(f"{url} returned HTTP {exc.code}: {details}") from exc
    except (TimeoutError, SocketTimeout) as exc:
        raise ResearchClientError(
            f"{url} request timed out after {settings.provider_runtime.request_timeout_seconds}s"
        ) from exc
    except URLError as exc:
        raise ResearchClientError(f"{url} request failed: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResearchClientError(f"{url} returned non-JSON data") from exc
