from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class ProbeResult:
    name: str
    ok: bool
    status_code: int
    latency_ms: float
    detail: str = ""


def _request(
    *,
    name: str,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object] | None = None,
) -> ProbeResult:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    if body is not None:
        headers = {**headers, "Content-Type": "application/json"}
    request = Request(url=url, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
            latency_ms = (time.perf_counter() - started) * 1000
            return ProbeResult(name=name, ok=True, status_code=response.status, latency_ms=latency_ms)
    except HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return ProbeResult(name=name, ok=False, status_code=exc.code, latency_ms=latency_ms, detail=str(exc))
    except URLError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return ProbeResult(name=name, ok=False, status_code=0, latency_ms=latency_ms, detail=str(exc.reason))


def build_trip_payload() -> dict[str, object]:
    return {
        "origin_city": "Bengaluru",
        "destination": "Mysuru",
        "start_date": "2026-05-10",
        "end_date": "2026-05-12",
        "traveler_count": 2,
        "trip_purpose": "leisure",
        "total_budget": 12000,
        "budget_tier": "mid_range",
        "pace": "balanced",
        "interests": ["food", "culture"],
        "accommodation_preference": "hotel",
        "transport_preference": "train",
        "constraints": {
            "dietary_restrictions": [],
            "accessibility_needs": [],
            "child_friendly": False,
            "elderly_travelers": False,
            "remote_work_needs": False,
            "notes": "Load test request.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a basic load probe against the Travel Planner API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL for the API.")
    parser.add_argument("--requests", type=int, default=10, help="Number of requests to send.")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrent workers.")
    parser.add_argument("--api-key", default="dev-local-api-key", help="API key header value.")
    parser.add_argument("--actor-id", default="load-tester@example.com", help="Actor ID header value.")
    parser.add_argument("--actor-role", default="operator", help="Actor role header value.")
    parser.add_argument(
        "--target",
        choices=("health", "trips"),
        default="health",
        help="Target endpoint to probe.",
    )
    args = parser.parse_args()

    headers = {
        "X-API-Key": args.api_key,
        "X-Actor-ID": args.actor_id,
        "X-Actor-Role": args.actor_role,
    }

    if args.target == "health":
        task: Callable[[], ProbeResult] = lambda: _request(
            name="health",
            method="GET",
            url=f"{args.base_url}/api/health",
            headers=headers,
        )
    else:
        payload = build_trip_payload()
        task = lambda: _request(
            name="create_trip",
            method="POST",
            url=f"{args.base_url}/api/trips",
            headers=headers,
            payload=payload,
        )

    results: list[ProbeResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = [executor.submit(task) for _ in range(max(1, args.requests))]
        for future in as_completed(futures):
            results.append(future.result())

    latencies = [item.latency_ms for item in results]
    failures = [item for item in results if not item.ok]
    print(
        json.dumps(
            {
                "target": args.target,
                "requests": len(results),
                "failures": len(failures),
                "success_rate": round((len(results) - len(failures)) / len(results), 4),
                "p50_latency_ms": round(statistics.median(latencies), 2) if latencies else 0.0,
                "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 2) if latencies else 0.0,
                "max_latency_ms": round(max(latencies), 2) if latencies else 0.0,
                "failure_details": [item.detail for item in failures[:5]],
            },
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
