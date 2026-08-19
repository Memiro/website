from http import HTTPStatus

from django.test import Client


def test_home_responds_with_html(client: Client) -> None:
    """Главная отдаёт HTML-заглушку."""
    response = client.get("/")

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Type"].startswith("text/html")
    assert "memiro" in response.content.decode()
