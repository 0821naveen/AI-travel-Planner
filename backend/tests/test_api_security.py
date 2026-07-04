from fastapi.testclient import TestClient

from src.core.config import AppSettings, DatabaseSettings, SecuritySettings, Settings
from src.main import create_app


def build_test_settings() -> Settings:
    return Settings(
        app=AppSettings(environment="test"),
        database=DatabaseSettings(url="sqlite+pysqlite:///:memory:"),
        security=SecuritySettings(enabled=False),
    )


def test_health_endpoint_available_without_auth_by_default():
    client = TestClient(create_app(build_test_settings()))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"


def test_trip_endpoint_requires_api_key_when_security_enabled():
    settings = Settings(
        app=AppSettings(environment="test"),
        database=DatabaseSettings(url="sqlite+pysqlite:///:memory:"),
        security=SecuritySettings(enabled=True, api_keys=["test-api-key"]),
    )
    client = TestClient(create_app(settings))
    response = client.post("/api/trips", json={})
    assert response.status_code == 401
