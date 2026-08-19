from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.mark.django_db
def test_admin_opens_for_superuser(client: Client) -> None:
    """Суперпользователь создаётся, админка открывается."""
    user_model = get_user_model()
    user_model.objects.create_superuser(
        username="owner",
        email="owner@example.com",
        password="owner-password",
    )

    assert client.login(username="owner", password="owner-password")
    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.OK


def test_admin_requires_login(client: Client) -> None:
    """Аноним отправляется на страницу входа."""
    response = client.get("/admin/", follow=True)

    assert response.status_code == HTTPStatus.OK
    assert "/admin/login/" in response.redirect_chain[-1][0]
