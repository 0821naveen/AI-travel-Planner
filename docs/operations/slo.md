# SLOs

## Service Objectives

The service-level objectives for this repo are:

- `API health availability`: 99.9% monthly for `/api/health`
- `Synchronous planning success rate`: 99.0% weekly for `POST /api/trips`
- `Async run completion rate`: 99.0% weekly for queued workflow runs
- `P95 sync plan latency`: under 30 seconds
- `P95 async run completion time`: under 5 minutes
- `Dead-letter rate`: under 1% of async workflow runs per week
- `Operator review turnaround`: 90% of `pending` review items resolved within 4 business hours

## Error Budget

- Availability error budget: `0.1%` monthly
- Sync planning failure budget: `1.0%` weekly
- Async dead-letter budget: `1.0%` weekly

If any budget is exhausted:

- freeze non-critical releases
- prioritize remediation over new features
- run an incident review

## Signals

Primary signals come from:

- `/api/admin/observability/metrics`
- `/api/admin/observability/alerts`
- `/api/admin/runs/{run_id}/trace`
- structured JSON logs
- audit events

## Review Cadence

- daily: operator review queue and active alerts
- weekly: failure-rate, latency, retry, and dead-letter trends
- release time: eval suite, CI, and staging validation
