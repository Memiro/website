import os

import httpx

PUBLIC_URL = os.environ.get("MEMIRO_PUBLIC_URL", "http://127.0.0.1:8080")
OK_STATUS = 200


async def test_nginx_serves_the_server_rendered_storefront() -> None:
    """The public contour serves the Russian SSR storefront through nginx."""
    async with httpx.AsyncClient(base_url=PUBLIC_URL) as client:
        response = await client.get("/")

    assert response.status_code == OK_STATUS
    assert 'lang="ru"' in response.text
    assert "Мастерская зеркал Memiro" in response.text


async def test_nginx_serves_the_server_rendered_catalogue() -> None:
    """The public contour serves the catalogue as SSR HTML through nginx."""
    async with httpx.AsyncClient(base_url=PUBLIC_URL) as client:
        response = await client.get("/catalog/")

    assert response.status_code == OK_STATUS
    assert "Каталог зеркал" in response.text


async def test_nginx_keeps_the_api_under_its_public_prefix() -> None:
    """The public contour keeps the API liveness endpoint under /api/."""
    async with httpx.AsyncClient(base_url=PUBLIC_URL) as client:
        response = await client.get("/api/internal/alive")

    assert response.status_code == OK_STATUS
    assert response.json() == {"status": "ok"}
