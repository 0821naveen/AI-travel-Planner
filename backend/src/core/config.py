from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional, Sequence

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment = Literal["dev", "staging", "prod", "test"]
BACKEND_DIR = Path(__file__).resolve().parents[2]
BASE_DIR = BACKEND_DIR.parent if BACKEND_DIR.name == "backend" else BACKEND_DIR


class AppSettings(BaseModel):
    name: str = "Travel Planner API"
    version: str = "0.1.0"
    environment: AppEnvironment = "dev"


class ApiSettings(BaseModel):
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["GET", "POST"])
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-API-Key", "X-Request-ID", "X-Actor-ID", "X-Actor-Role"]
    )


class LoggingSettings(BaseModel):
    level: str = "INFO"


class ProviderRuntimeSettings(BaseModel):
    request_timeout_seconds: int = 30
    tavily_max_results: int = 4
    openai_temperature: float = 0.2
    weather_forecast_max_days: int = 14
    serpapi_hotel_limit: int = 5


class SecuritySettings(BaseModel):
    enabled: bool = True
    api_key_header: str = "X-API-Key"
    actor_id_header: str = "X-Actor-ID"
    actor_role_header: str = "X-Actor-Role"
    api_keys: list[str] = Field(default_factory=lambda: ["dev-local-api-key"])
    rate_limit_per_minute: int = 120
    trusted_proxy_headers: bool = False
    trusted_proxy_ips: list[str] = Field(default_factory=list)
    allow_healthcheck_without_auth: bool = True
    minimum_secret_length: int = 20


class AuthSettings(BaseModel):
    token_header: str = "Authorization"
    token_ttl_hours: int = 168
    password_min_length: int = 8
    session_signing_secret: Optional[str] = None


class AsyncSettings(BaseModel):
    max_workers: int = 2


class DatabaseSettings(BaseModel):
    url: str = "postgresql+psycopg://travel_planner:travel_planner@localhost:5432/travel_planner"


class RedisSettings(BaseModel):
    url: str = "redis://localhost:6379/0"


class WorkflowRuntimeSettings(BaseModel):
    queue_name: str = "travel-planner-runs"
    dead_letter_queue_name: str = "travel-planner-dead-letter"
    max_retries: int = 3
    retry_delay_seconds: int = 30
    job_timeout_seconds: int = 300
    require_worker_on_startup: bool = False
    require_current_migrations_on_startup: bool = True


class MemorySettings(BaseModel):
    trip_history_retrieval_enabled: bool = False
    vector_store_enabled: bool = False
    state_version: int = 2


class ObservabilitySettings(BaseModel):
    metrics_lookback_hours: int = 24
    stuck_run_threshold_minutes: int = 15
    failure_rate_alert_threshold: float = 0.2
    provider_failure_alert_threshold: int = 5
    dead_letter_alert_threshold: int = 1


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    provider_runtime: ProviderRuntimeSettings = Field(default_factory=ProviderRuntimeSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    async_processing: AsyncSettings = Field(default_factory=AsyncSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    workflow_runtime: WorkflowRuntimeSettings = Field(default_factory=WorkflowRuntimeSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    weatherapi_api_key: Optional[str] = None
    serpapi_api_key: Optional[str] = None
    aviationstack_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        extra="ignore",
        env_nested_delimiter="__",
    )

    @model_validator(mode="after")
    def validate_runtime_requirements(self) -> "Settings":
        environment = self.app.environment
        database_url = self.database.url.strip()

        if not database_url:
            raise ValueError("DATABASE__URL must be configured.")

        if environment in {"dev", "staging", "prod"} and not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE__URL must use the 'postgresql+psycopg://' driver outside the test environment.")

        if environment == "test" and not (
            database_url.startswith("sqlite") or database_url.startswith("postgresql+psycopg://")
        ):
            raise ValueError("Test environment DATABASE__URL must use sqlite or postgresql+psycopg.")

        if not self.openai_model.strip():
            raise ValueError("OPENAI_MODEL must not be empty.")

        if environment in {"staging", "prod"}:
            missing = [
                name
                for name, value in {
                    "OPENAI_API_KEY": self.openai_api_key,
                    "TAVILY_API_KEY": self.tavily_api_key,
                    "WEATHERAPI_API_KEY": self.weatherapi_api_key,
                    "SERPAPI_API_KEY": self.serpapi_api_key,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"Missing required provider configuration for {environment}: {', '.join(missing)}")

            if not self.redis.url.strip():
                raise ValueError(f"REDIS__URL must be configured for {environment}.")

        if self.security.enabled and not self.security.api_keys:
            raise ValueError("SECURITY__API_KEYS must be configured when SECURITY__ENABLED=true.")

        if len(set(self.security.api_keys)) != len(self.security.api_keys):
            raise ValueError("SECURITY__API_KEYS must not contain duplicates.")

        if environment in {"staging", "prod"} and "dev-local-api-key" in self.security.api_keys:
            raise ValueError("Default development API keys are not allowed in staging or production.")

        if environment in {"staging", "prod"}:
            invalid_api_keys = [
                key
                for key in self.security.api_keys
                if len(key.strip()) < self.security.minimum_secret_length or _looks_like_placeholder_secret(key)
            ]
            if invalid_api_keys:
                raise ValueError(
                    "SECURITY__API_KEYS must use non-placeholder values that meet the minimum secret length "
                    f"of {self.security.minimum_secret_length} in {environment}."
                )

            weak_provider_secrets = [
                name
                for name, value in {
                    "OPENAI_API_KEY": self.openai_api_key,
                    "TAVILY_API_KEY": self.tavily_api_key,
                    "WEATHERAPI_API_KEY": self.weatherapi_api_key,
                    "SERPAPI_API_KEY": self.serpapi_api_key,
                }.items()
                if value is None
                or len(value.strip()) < self.security.minimum_secret_length
                or _looks_like_placeholder_secret(value)
            ]
            if weak_provider_secrets:
                raise ValueError(
                    f"Provider secrets must use non-placeholder values with length >= {self.security.minimum_secret_length}: "
                    + ", ".join(weak_provider_secrets)
                )

        signing_secret = self.auth.session_signing_secret or (self.security.api_keys[0] if self.security.api_keys else "")
        if environment in {"staging", "prod"} and (
            len(signing_secret.strip()) < self.security.minimum_secret_length
            or _looks_like_placeholder_secret(signing_secret)
        ):
            raise ValueError(
                "AUTH__SESSION_SIGNING_SECRET must be configured with a strong non-placeholder value in staging or prod."
            )

        if environment == "prod" and not self.security.enabled:
            raise ValueError("Production configuration must enable API key security.")

        return self


def _looks_like_placeholder_secret(value: str) -> bool:
    normalized = value.strip().lower()
    placeholder_markers = (
        "changeme",
        "change-me",
        "replace-me",
        "replace_this",
        "example",
        "your_",
        "dummy",
        "test-key",
        "sample",
    )
    return any(marker in normalized for marker in placeholder_markers)


def _environment_hint(explicit_environment: AppEnvironment | None = None) -> AppEnvironment:
    if explicit_environment is not None:
        return explicit_environment

    raw_environment = os.getenv("APP__ENVIRONMENT", "dev").strip().lower()
    if raw_environment not in {"dev", "staging", "prod", "test"}:
        raise ValueError(f"Unsupported APP__ENVIRONMENT value: {raw_environment}")
    return raw_environment  # type: ignore[return-value]


def _env_files(environment: AppEnvironment) -> tuple[str, ...]:
    candidates = (
        BACKEND_DIR / ".env",
        BACKEND_DIR / f".env.{environment}",
        BASE_DIR / ".env",
    )
    return tuple(str(path) for path in candidates if path.exists())


def build_settings(
    *,
    environment: AppEnvironment | None = None,
    env_files: Sequence[str] | None = None,
    **overrides: object,
) -> Settings:
    resolved_environment = _environment_hint(environment)
    resolved_env_files = tuple(env_files) if env_files is not None else _env_files(resolved_environment)

    app_payload = overrides.pop("app", None)
    if isinstance(app_payload, AppSettings):
        app_settings = app_payload.model_copy(update={"environment": resolved_environment})
    elif isinstance(app_payload, dict):
        app_settings = AppSettings(**app_payload, environment=resolved_environment)
    else:
        app_settings = AppSettings(environment=resolved_environment)

    return Settings(
        _env_file=resolved_env_files or None,
        _env_file_encoding="utf-8",
        app=app_settings,
        **overrides,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return build_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
