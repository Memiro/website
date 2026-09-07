"""The owner fills the gallery of a product from its card, and the files go to the storage (тикет 08)."""

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Manager
from django.test import AsyncClient

from memiro.application.errors.catalog import ProductImageNotFoundError
from memiro.entities.common.identifiers import ProductId
from memiro.entities.errors.product import DuplicateProductImageError
from memiro.presentation.django_admin.refusals import REFUSAL_MESSAGES
from tests.integration.admin.arrange import arranged_photo, arranged_product, product_post

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

APP = "memiro"
PHOTO = b"\xff\xd8\xff\xd9"
# Every refusal the gallery half of the card can meet, spelled out rather
# than collected from the modules: a code missing from the table is silent.
GALLERY_REFUSALS = (ProductImageNotFoundError, DuplicateProductImageError)


@dataclass(frozen=True, slots=True)
class Photographed:
    """The product one test hangs its gallery on, and the name its card carries."""

    id: ProductId
    name: str


@pytest.fixture
def photographed() -> Photographed:
    """Enter a product of the demo section: the admin's database outlives one test, its addresses are unique."""
    name = f"Зеркало под фотографии {uuid4().hex[:8]}"
    return Photographed(id=arranged_product(name=name), name=name)


def _images() -> Manager[Any]:
    """Reach the photo mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "ProductImage").objects)


def _card_url(product_id: ProductId) -> str:
    return f"/admin/{APP}/product/{product_id}/change/"


def _stored_files(root: Path) -> set[str]:
    """Read what the storage holds on the volume the whole admin suite shares."""
    return {file.name for file in root.iterdir()}


def _delete_url(product_id: ProductId) -> str:
    return f"/admin/{APP}/product/{product_id}/delete/"


def _card(product: Photographed, **fields: list[Any]) -> dict[str, Any]:
    """Spell the card of the photographed product with the gallery half filled in."""
    return product_post(name=product.name) | fields


async def _keys(product_id: ProductId) -> set[str]:
    """Read the gallery of one product as the storefront reads it."""
    return {image.key async for image in _images().filter(product_id=product_id)}


async def test_the_owner_uploads_a_photo_from_the_product_card(
    owner_client: AsyncClient,
    admin_media_root: Path,
    photographed: Photographed,
) -> None:
    """A photo picked on the card reaches the storage through the port, and the gallery names it."""
    response = await owner_client.post(
        _card_url(photographed.id),
        _card(photographed, photos=[SimpleUploadedFile("mirror.jpg", PHOTO, content_type="image/jpeg")]),
    )

    assert response.status_code == HTTPStatus.FOUND
    stored = await _keys(photographed.id)
    assert len(stored) == 1
    assert (admin_media_root / stored.pop()).read_bytes() == PHOTO


async def test_the_owner_takes_a_photo_off_the_product_card(
    owner_client: AsyncClient,
    admin_media_root: Path,
    photographed: Photographed,
) -> None:
    """A photo the owner struck out leaves the gallery and the storage with it."""
    uploaded = arranged_photo(photographed.id, content=PHOTO)

    response = await owner_client.post(_card_url(photographed.id), _card(photographed, remove_photos=[uploaded]))

    assert response.status_code == HTTPStatus.FOUND
    assert await _keys(photographed.id) == set()
    assert not (admin_media_root / uploaded).exists()


async def test_a_file_that_is_not_a_photo_never_reaches_the_storage(
    owner_client: AsyncClient,
    photographed: Photographed,
) -> None:
    """The card takes photos: anything else comes back on the form, and the gallery stays empty."""
    response = await owner_client.post(
        _card_url(photographed.id),
        _card(photographed, photos=[SimpleUploadedFile("prices.pdf", PHOTO, content_type="application/pdf")]),
    )

    assert response.status_code == HTTPStatus.OK
    assert await _keys(photographed.id) == set()


async def test_the_card_takes_no_photo_from_anybody_who_may_not_change_the_product(
    clerk_client: AsyncClient,
    admin_media_root: Path,
    photographed: Photographed,
) -> None:
    """Signing in is not the permission: staff without it uploads nothing and the volume stays as it was."""
    before = await asyncio.to_thread(_stored_files, admin_media_root)

    response = await clerk_client.post(
        _card_url(photographed.id),
        _card(photographed, photos=[SimpleUploadedFile("mirror.jpg", PHOTO, content_type="image/jpeg")]),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert await _keys(photographed.id) == set()
    assert await asyncio.to_thread(_stored_files, admin_media_root) == before


async def test_the_photos_of_a_removed_product_leave_the_storage_with_it(
    owner_client: AsyncClient,
    admin_media_root: Path,
    photographed: Photographed,
) -> None:
    """A product is removed with its gallery: the rows go by cascade and the files go with them."""
    uploaded = arranged_photo(photographed.id, content=PHOTO)

    response = await owner_client.post(_delete_url(photographed.id), {"post": "yes"})

    assert response.status_code == HTTPStatus.FOUND
    assert await _keys(photographed.id) == set()
    assert not (admin_media_root / uploaded).exists()


def test_every_refusal_the_gallery_can_meet_is_named_in_the_owner_s_words() -> None:
    """A code missing from the table shows «Запись отклонена.» and is invisible without this check."""
    named = REFUSAL_MESSAGES.keys()

    assert set(GALLERY_REFUSALS) <= named
