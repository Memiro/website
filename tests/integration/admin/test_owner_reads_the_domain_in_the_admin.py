"""The owner signs in with Django's own auth and reads the domain (decision 11).

The screens are read-only in this slice: the write paths arrive ticket by
ticket, each one through the interactor the API already calls (ADR-0012).
"""

# django-stubs makes Field and InlineModelAdmin generic, but the runtime
# classes are not subscriptable: the annotations must stay unevaluated.
from __future__ import annotations

from http import HTTPStatus

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.db.models import Model
from django.db.models.options import Options
from django.test import AsyncClient

from tests.integration.admin.conftest import OWNER_PASSWORD, OWNER_USERNAME

LOGIN_URL = "/admin/login/"

pytestmark = pytest.mark.usefixtures("admin_site")


APP = "memiro"


def _inline_model(inline: type[InlineModelAdmin[Model, Model]]) -> type[Model]:
    """Name the child model an inline shows on the card of its parent."""
    # `model` is declared on the instance, but an inline is registered as a
    # class and Django reads it off the class the same way.
    return inline.model  # pyright: ignore[reportGeneralTypeIssues]


def _meta(mirror: type[Model]) -> Options[Model]:
    """Reach a model's Meta, which is Django's documented way to ask about a table."""
    return mirror._meta  # noqa: SLF001


def _registered_mirrors() -> list[type[Model]]:
    return [mirror for mirror in admin.site._registry if _meta(mirror).app_label == APP]  # noqa: SLF001  # ``_registry`` is Django's documented admin API


def _changelist_urls() -> list[str]:
    return [f"/admin/{APP}/{_meta(mirror).model_name}/" for mirror in _registered_mirrors()]


def _inlined_models() -> set[str]:
    return {
        str(_meta(_inline_model(inline)).model_name)
        for options in admin.site._registry.values()  # noqa: SLF001  # Django's documented admin API
        for inline in options.inlines
    }


async def test_a_stranger_is_sent_to_the_login_page() -> None:
    """An unauthenticated visitor never sees a changelist."""
    client = AsyncClient()

    response = await client.get("/admin/")

    assert response.status_code == HTTPStatus.FOUND
    assert response.headers["Location"].startswith(LOGIN_URL)


async def test_the_owner_signs_in_with_the_account_the_command_created() -> None:
    """``ensure_superuser`` makes exactly the account the owner logs in with."""
    client = AsyncClient()

    signed_in = await client.alogin(username=OWNER_USERNAME, password=OWNER_PASSWORD)

    assert signed_in


async def test_every_mirror_is_reachable_as_a_changelist_or_an_inline() -> None:
    """No mirror is dead weight: the owner reaches every domain table on some screen."""
    registered = {str(_meta(mirror).model_name) for mirror in _registered_mirrors()}

    unreachable = (
        {
            mirror._meta.model_name  # noqa: SLF001
            for mirror in apps.get_app_config(APP).get_models()
        }
        - registered
        - _inlined_models()
    )

    assert unreachable == set()


async def test_the_owner_sees_a_changelist_for_every_registered_mirror() -> None:
    """Every registered mirror's changelist renders."""
    client = AsyncClient()
    await client.alogin(username=OWNER_USERNAME, password=OWNER_PASSWORD)

    statuses = {url: (await client.get(url)).status_code for url in _changelist_urls()}

    assert statuses == dict.fromkeys(_changelist_urls(), HTTPStatus.OK)


async def test_the_owner_is_offered_no_form_to_add_a_domain_row() -> None:
    """The add view of a mirror refuses: the domain is written through interactors."""
    client = AsyncClient()
    await client.alogin(username=OWNER_USERNAME, password=OWNER_PASSWORD)

    response = await client.get("/admin/memiro/product/add/")

    assert response.status_code == HTTPStatus.FORBIDDEN


async def test_the_owner_opens_a_product_card_with_the_child_rows_inlined(primed_catalog: None) -> None:  # noqa: ARG001
    """Photos and declared values have no changelist of their own: the card is where they live."""
    client = AsyncClient()
    await client.alogin(username=OWNER_USERNAME, password=OWNER_PASSWORD)
    product = await apps.get_model(APP, "Product").objects.afirst()

    response = await client.get(f"/admin/{APP}/product/{product.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    assert "Объявленные значения" in response.content.decode()
    assert "Фотографии" in response.content.decode()


async def test_the_owner_opens_the_pricing_settings_with_the_surcharge_steps_inlined(
    primed_catalog: None,  # noqa: ARG001
) -> None:
    """The steps of the size surcharge are read inside the object that owns them (ADR-0010)."""
    client = AsyncClient()
    await client.alogin(username=OWNER_USERNAME, password=OWNER_PASSWORD)
    settings_row = await apps.get_model(APP, "PricingSettings").objects.afirst()

    response = await client.get(f"/admin/{APP}/pricingsettings/{settings_row.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    assert "Ступени наценки" in response.content.decode()
