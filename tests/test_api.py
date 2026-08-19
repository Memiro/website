from http import HTTPStatus

from django.test import Client


def test_ping_returns_typed_json(client: Client) -> None:
    """Пробный эндпоинт django-modern-rest отвечает валидным JSON."""
    response = client.get("/api/ping")

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Type"].startswith("application/json")
    assert response.json() == {"status": "ok"}


def test_ping_is_in_openapi_schema(client: Client) -> None:
    """Пробный эндпоинт отражён в OpenAPI-схеме."""
    response = client.get("/api/openapi/schema.json")

    assert response.status_code == HTTPStatus.OK
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert "/api/ping" in schema["paths"]
    assert "get" in schema["paths"]["/api/ping"]
