# Runbooks

## Release Runbook

1. Confirm CI is green.
2. Confirm `python -m src.evals.runner --strict` is green.
3. Confirm review queue is not blocked by a current incident.
4. Run staging deployment workflow.
5. Verify:
   - `/api/health/readiness`
   - `/api/health/dependencies`
   - `/api/admin/observability/alerts`
   - one smoke trip run
6. Promote the tagged release through production workflow.

## Stuck Run Runbook

Trigger:

- `stuck_runs_detected` alert

Response:

1. Inspect `/api/admin/runs/{run_id}/trace`.
2. Check worker presence from `/api/health/dependencies`.
3. Check Redis and DB readiness.
4. If the worker is unhealthy, restart workers before rerunning trips.
5. Cancel or rerun affected runs through the run APIs.
6. Record the incident and link the affected run IDs.

## Provider Degradation Runbook

Trigger:

- `provider_failures_high` alert

Response:

1. Inspect provider-specific failures in observability metrics and run traces.
2. Confirm whether failures are isolated to one provider endpoint.
3. If failures are systemic, reduce release activity and reroute review items for human approval.
4. Re-run failed trips after provider recovery.
5. If degradation persists, disable affected features at the environment level.

## Dead-Letter Runbook

Trigger:

- `dead_letter_runs_present` alert

Response:

1. Inspect the affected run traces and audit events.
2. Determine whether the cause is provider failure, runtime failure, or invalid input.
3. If transient, rerun after recovery.
4. If systemic, halt promotion and open an incident.
5. Capture failed payload patterns for regression coverage.

## Secret Rotation Runbook

1. Add the new secret in the target environment.
2. Validate staging with the new secret before removing the old one.
3. Update the environment-specific deployment secret store.
4. Deploy staging, then production.
5. Remove the old secret after successful production validation.
