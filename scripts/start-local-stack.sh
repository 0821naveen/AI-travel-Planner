#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://localhost:8000/api/health}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker-compose.yml}"
START_TIMEOUT_SECONDS="${START_TIMEOUT_SECONDS:-180}"

log() {
  printf '[start-local-stack] %s\n' "$1"
}

load_env_value() {
  local key="$1"
  local file="$2"

  [ -f "$file" ] || return 1

  awk -F= -v target="$key" '
    /^[[:space:]]*#/ { next }
    $0 !~ /=/ { next }
    {
      current_key = $1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", current_key)
      if (current_key != target) {
        next
      }
      value = substr($0, index($0, "=") + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' "$file"
}

export_provider_key() {
  local key="$1"
  local value=""

  if [ -n "${!key:-}" ]; then
    return 0
  fi

  value="$(load_env_value "$key" "$ROOT_DIR/backend/.env" || true)"
  if [ -z "$value" ]; then
    value="$(load_env_value "$key" "$ROOT_DIR/.env" || true)"
  fi

  if [ -n "$value" ]; then
    export "$key=$value"
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local elapsed=0

  until curl --silent --show-error --fail "$url" >/dev/null 2>&1; do
    sleep 2
    elapsed=$((elapsed + 2))
    if [ "$elapsed" -ge "$START_TIMEOUT_SECONDS" ]; then
      log "Timed out waiting for ${label} at ${url}"
      return 1
    fi
  done
}

open_browser() {
  local url="$1"

  if command -v open >/dev/null 2>&1; then
    open "$url"
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
    return 0
  fi

  log "No supported browser opener found. Open this URL manually: $url"
}

require_command docker
require_command curl

export_provider_key OPENAI_API_KEY
export_provider_key TAVILY_API_KEY
export_provider_key WEATHERAPI_API_KEY

if ! docker info >/dev/null 2>&1; then
  log "Docker is not running. Start Docker Desktop and retry."
  exit 1
fi

log "Starting backend, worker, frontend, postgres, and redis with Docker Compose"
docker compose -f "$COMPOSE_FILE" up --build -d

log "Waiting for backend health endpoint"
wait_for_url "$BACKEND_HEALTH_URL" "backend"

log "Waiting for frontend"
wait_for_url "$FRONTEND_URL" "frontend"

log "Opening ${FRONTEND_URL}"
open_browser "$FRONTEND_URL"

log "Stack is ready"
