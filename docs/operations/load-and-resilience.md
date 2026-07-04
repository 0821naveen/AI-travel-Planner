# Load And Resilience

## Automated Coverage

The backend resilience test suite covers:

- async retry scheduling
- dead-letter behavior after retry exhaustion
- observability alerts for failure and stuck-run conditions

Relevant tests:

- `backend/tests/test_runtime_resilience.py`
- `backend/tests/test_observability.py`

## Manual Load Probe

Use the bundled probe against a running environment:

```bash
cd backend
python3 scripts/load_test.py --base-url http://127.0.0.1:8000 --target health --requests 20 --concurrency 5
python3 scripts/load_test.py --base-url http://127.0.0.1:8000 --target trips --requests 5 --concurrency 2
```

The script prints:

- success rate
- p50 latency
- p95 latency
- max latency
- sample failure details

## Resilience Drills

Recommended drills before production promotion:

1. stop workers and confirm `stuck_runs_detected`
2. break provider credentials in staging and confirm `provider_failures_high`
3. force repeated workflow failure and confirm dead-letter behavior
4. restore dependencies and verify rerun and recovery paths
