import os

import httpx

PUBLIC_URL = os.environ.get("MEMIRO_PUBLIC_URL", "http://127.0.0.1:8080")
OK_STATUS = 200


async def test_nginx_serves_the_admin_login_page_under_its_public_prefix() -> None:
    """The public contour puts the owner's admin behind /admin/."""
    async with httpx.AsyncClient(base_url=PUBLIC_URL) as client:
        response = await client.get("/admin/login/")

    assert response.status_code == OK_STATUS
    assert "csrfmiddlewaretoken" in response.text


async def test_nginx_serves_the_admin_static_collectstatic_produced() -> None:
    """The static of the admin comes from nginx, not from the WSGI process."""
    async with httpx.AsyncClient(base_url=PUBLIC_URL) as client:
        response = await client.get("/admin-static/admin/css/base.css")

    assert response.status_code == OK_STATUS
    assert response.headers["content-type"].startswith("text/css")
