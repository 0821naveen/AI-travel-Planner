import pytest

from src.core.config import (
    ApiSettings,
    AppSettings,
    AsyncSettings,
    DatabaseSettings,
    LoggingSettings,
    ProviderRuntimeSettings,
    SecuritySettings,
    Settings,
)


def test_staging_requires_provider_keys():
    with pytest.raises(ValueError):
        Settings(
            app=AppSettings(environment="staging"),
            database=DatabaseSettings(url="postgresql+psycopg://user:pass@localhost:5432/travel_planner"),
        )


def test_production_requires_security_enabled():
    with pytest.raises(ValueError):
        Settings(
            app=AppSettings(environment="prod"),
            database=DatabaseSettings(url="postgresql+psycopg://user:pass@localhost:5432/travel_planner"),
            security=SecuritySettings(enabled=False),
            openai_api_key="prod-openai-key-1234567890",
            tavily_api_key="prod-tavily-key-1234567890",
            weatherapi_api_key="prod-weather-key-1234567890",
        )


def test_test_environment_allows_sqlite():
    settings = Settings(
        app=AppSettings(environment="test"),
        api=ApiSettings(),
        logging=LoggingSettings(),
        provider_runtime=ProviderRuntimeSettings(),
        async_processing=AsyncSettings(),
        security=SecuritySettings(enabled=False),
        database=DatabaseSettings(url="sqlite+pysqlite:///:memory:"),
    )

    assert settings.database.url.startswith("sqlite")


def test_staging_rejects_placeholder_secrets():
    with pytest.raises(ValueError):
        Settings(
            app=AppSettings(environment="staging"),
            database=DatabaseSettings(url="postgresql+psycopg://user:pass@localhost:5432/travel_planner"),
            security=SecuritySettings(api_keys=["replace-me-api-key-12345"]),
            openai_api_key="your_openai_key_1234567890",
            tavily_api_key="prod-tavily-key-1234567890",
            weatherapi_api_key="prod-weather-key-1234567890",
        )


def test_staging_requires_minimum_secret_length():
    with pytest.raises(ValueError):
        Settings(
            app=AppSettings(environment="staging"),
            database=DatabaseSettings(url="postgresql+psycopg://user:pass@localhost:5432/travel_planner"),
            security=SecuritySettings(api_keys=["short-key"]),
            openai_api_key="prod-openai-key-1234567890",
            tavily_api_key="prod-tavily-key-1234567890",
            weatherapi_api_key="prod-weather-key-1234567890",
        )
