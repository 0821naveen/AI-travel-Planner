# Deployment

## Environments

- `dev`: local development, permissive defaults
- `staging`: release candidate validation
- `production`: protected release environment

## GitHub Workflows

- `.github/workflows/ci.yml`
- `.github/workflows/secrets-scan.yml`
- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-production.yml`

The staging and production workflows:

- validate backend lint, typing, tests, and evals
- validate frontend lint, typing, tests, and build
- package backend and frontend artifacts
- publish release metadata as build artifacts

## Secret Posture

Staging and production must not use:

- placeholder provider secrets
- short API keys
- duplicated API keys
- the default development API key

These checks are enforced by backend settings validation.

## Deployment Checklist

1. Ensure required environment secrets are present.
2. Run Alembic migrations before shifting traffic.
3. Validate `/api/health/readiness` and `/api/health/dependencies`.
4. Check `/api/admin/observability/alerts`.
5. Run a smoke trip creation flow.
6. Confirm worker registration and Redis connectivity.

## Rollback

Rollback requires:

1. redeploying the previous backend/frontend artifacts
2. restoring the previous environment configuration if a secret change caused the fault
3. verifying worker, Redis, DB, and alert health before reopening traffic
