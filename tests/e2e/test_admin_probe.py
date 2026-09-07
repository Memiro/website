import os

import httpx

PUBLIC_URL = os.environ.get("MEMIRO_PUBLIC_URL", "http://127.0.0.1:8080")
OK_STATUS = 200
FORBIDDEN_STATUS = 403
NOT_FOUND_STATUS = 404


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


async def test_nginx_serves_the_script_the_variant_builder_runs_on() -> None:
    """The panel of the product card is driven by static, and static is nginx's job (ADR-0011)."""
    async with httpx.AsyncClient(base_url=PUBLIC_URL) as client:
        script = await client.get("/admin-static/memiro/js/admin-variant-builder.js")
        styles = await client.get("/admin-static/memiro/css/admin-variants.css")

    assert script.status_code == OK_STATUS
    assert "DOMContentLoaded" in script.text
    assert styles.status_code == OK_STATUS
    assert styles.headers["content-type"].startswith("text/css")


async def test_nginx_serves_the_volume_the_admin_puts_product_photos_on() -> None:
    """Photos come off the media volume at the edge: nothing about /media/ reaches the storefront."""
    async with httpx.AsyncClient(base_url=PUBLIC_URL) as client:
        response = await client.get("/media/no-such-photo.jpg")

    assert response.status_code == NOT_FOUND_STATUS
    assert "nginx" in response.text


async def test_the_edge_keeps_the_port_the_admin_checks_the_origin_against() -> None:
    """A form of the admin survives the edge: nginx must pass the host with its port.

    ``$host`` drops it, and Django then compares the browser's Origin — port
    and all — against a host without one and refuses every write with a 403.
    The credentials here are deliberately wrong: what is under test is that
    the answer is the login form again and not the CSRF refusal.
    """
    async with httpx.AsyncClient(base_url=PUBLIC_URL) as client:
        page = await client.get("/admin/login/")
        token = page.cookies["csrftoken"]
        response = await client.post(
            "/admin/login/",
            data={"csrfmiddlewaretoken": token, "username": "nobody", "password": "wrong"},
            headers={"Origin": PUBLIC_URL, "Referer": f"{PUBLIC_URL}/admin/login/"},
        )

    assert response.status_code != FORBIDDEN_STATUS
    assert response.status_code == OK_STATUS
