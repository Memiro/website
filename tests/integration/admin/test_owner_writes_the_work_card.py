"""The owner keeps the gallery «Наши работы» from its own card (тикет 01)."""

import asyncio
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Manager
from django.test import AsyncClient

from memiro.application.errors.catalog import ProductNotFoundError, WorkNotFoundError
from memiro.entities.common.identifiers import WorkId
from memiro.presentation.django_admin.refusals import REFUSAL_MESSAGES
from tests.common.factory.catalog import PRODUCT
from tests.integration.admin.arrange import arranged_work, work_post

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

APP = "memiro"
PHOTO = b"\xff\xd8\xff\xd9"
SECOND_PHOTO = b"\xff\xd8\x00\xd9"
# Every refusal the work card can meet, spelled out rather than collected from
# the modules: a code missing from the table is silent.
WORK_REFUSALS = (WorkNotFoundError, ProductNotFoundError)

ADD_URL = f"/admin/{APP}/work/add/"
LOGIN_URL = "/admin/login/"


def _works() -> Manager[Any]:
    """Reach the work mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model(APP, "Work").objects)


def _card_url(work_id: WorkId) -> str:
    return f"/admin/{APP}/work/{work_id}/change/"


def _delete_url(work_id: WorkId) -> str:
    return f"/admin/{APP}/work/{work_id}/delete/"


def _uploaded(content: bytes = PHOTO) -> SimpleUploadedFile:
    return SimpleUploadedFile("installed.jpg", content, content_type="image/jpeg")


def _stored_files(root: Path) -> set[str]:
    """Read what the storage holds on the volume the whole admin suite shares."""
    return {file.name for file in root.iterdir()}


async def test_the_owner_enters_a_work_from_the_card(
    owner_client: AsyncClient,
    admin_media_root: Path,
) -> None:
    """A work picked on the card reaches the storage through the port, and the gallery names it."""
    title = f"Работа {uuid4().hex[:8]}"

    response = await owner_client.post(ADD_URL, work_post(title=title, product=PRODUCT) | {"photo": _uploaded()})

    assert response.status_code == HTTPStatus.FOUND
    entered = await _works().aget(title=title)
    assert entered.product_id == PRODUCT
    assert (admin_media_root / entered.photo_key).read_bytes() == PHOTO


async def test_the_owner_restates_a_work_without_touching_its_photograph(
    owner_client: AsyncClient,
    admin_media_root: Path,
) -> None:
    """An empty file field on a saved card keeps the picture the work stands on."""
    work_id = arranged_work(title=f"Работа {uuid4().hex[:8]}", content=PHOTO)
    entered = await _works().aget(pk=work_id)
    restated = f"Работа под новой подписью {uuid4().hex[:8]}"

    response = await owner_client.post(_card_url(work_id), work_post(title=restated, sort_order=4))

    assert response.status_code == HTTPStatus.FOUND
    saved = await _works().aget(pk=work_id)
    assert (saved.title, saved.sort_order, saved.photo_key) == (restated, 4, entered.photo_key)
    assert (admin_media_root / saved.photo_key).read_bytes() == PHOTO


async def test_a_photograph_the_owner_replaced_leaves_the_storage(
    owner_client: AsyncClient,
    admin_media_root: Path,
) -> None:
    """The picture nothing names any more is dropped, and the new one is what the row carries."""
    work_id = arranged_work(title=f"Работа {uuid4().hex[:8]}", content=PHOTO)
    entered = await _works().aget(pk=work_id)

    response = await owner_client.post(
        _card_url(work_id),
        work_post(title=entered.title) | {"photo": _uploaded(SECOND_PHOTO)},
    )

    assert response.status_code == HTTPStatus.FOUND
    saved = await _works().aget(pk=work_id)
    assert (admin_media_root / saved.photo_key).read_bytes() == SECOND_PHOTO
    assert not (admin_media_root / entered.photo_key).exists()


async def test_the_owner_takes_a_work_out_of_the_gallery(
    owner_client: AsyncClient,
    admin_media_root: Path,
) -> None:
    """A removed work leaves the gallery, and its photograph leaves the volume with it."""
    work_id = arranged_work(title=f"Работа {uuid4().hex[:8]}", content=PHOTO)
    entered = await _works().aget(pk=work_id)

    response = await owner_client.post(_delete_url(work_id), {"post": "yes"})

    assert response.status_code == HTTPStatus.FOUND
    assert not await _works().filter(pk=work_id).aexists()
    assert not (admin_media_root / entered.photo_key).exists()


async def test_a_file_that_is_not_a_photograph_never_reaches_the_storage(
    owner_client: AsyncClient,
    admin_media_root: Path,
) -> None:
    """The card takes photos: anything else comes back on the form, and the gallery stays as it was."""
    title = f"Работа {uuid4().hex[:8]}"
    before = await asyncio.to_thread(_stored_files, admin_media_root)

    response = await owner_client.post(
        ADD_URL,
        work_post(title=title) | {"photo": SimpleUploadedFile("prices.pdf", PHOTO, content_type="application/pdf")},
    )

    assert response.status_code == HTTPStatus.OK
    assert not await _works().filter(title=title).aexists()
    assert await asyncio.to_thread(_stored_files, admin_media_root) == before


async def test_a_new_work_without_a_photograph_is_refused_by_the_form(owner_client: AsyncClient) -> None:
    """A work is a photograph with a caption: the card of a new one asks for the file."""
    title = f"Работа {uuid4().hex[:8]}"

    response = await owner_client.post(ADD_URL, work_post(title=title))

    assert response.status_code == HTTPStatus.OK
    assert not await _works().filter(title=title).aexists()


async def test_the_gallery_takes_nothing_from_anybody_who_may_not_write_it(
    clerk_client: AsyncClient,
    admin_media_root: Path,
) -> None:
    """Signing in is not the permission: staff without it enters nothing and the volume stays as it was."""
    title = f"Работа {uuid4().hex[:8]}"
    before = await asyncio.to_thread(_stored_files, admin_media_root)

    response = await clerk_client.post(ADD_URL, work_post(title=title) | {"photo": _uploaded()})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert not await _works().filter(title=title).aexists()
    assert await asyncio.to_thread(_stored_files, admin_media_root) == before


async def test_the_card_of_a_saved_work_takes_nothing_from_anybody_who_may_not_write_it(
    clerk_client: AsyncClient,
    admin_media_root: Path,
) -> None:
    """Staff without the permission restates no work and replaces no photograph."""
    work_id = arranged_work(title=f"Работа {uuid4().hex[:8]}", content=PHOTO)
    entered = await _works().aget(pk=work_id)

    response = await clerk_client.post(
        _card_url(work_id),
        work_post(title="Чужая подпись") | {"photo": _uploaded(SECOND_PHOTO)},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    saved = await _works().aget(pk=work_id)
    assert (saved.title, saved.photo_key) == (entered.title, entered.photo_key)
    assert (admin_media_root / entered.photo_key).read_bytes() == PHOTO


async def test_the_gallery_keeps_the_work_staff_without_the_permission_deleted(clerk_client: AsyncClient) -> None:
    """Deletion is the same write: without the permission the work stays in the gallery."""
    work_id = arranged_work(title=f"Работа {uuid4().hex[:8]}", content=PHOTO)

    response = await clerk_client.post(_delete_url(work_id), {"post": "yes"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert await _works().filter(pk=work_id).aexists()


async def test_a_stranger_enters_no_work_into_the_gallery() -> None:
    """An unauthenticated POST is sent to the login page and leaves the gallery alone."""
    stranger = AsyncClient()
    title = f"Незваная работа {uuid4().hex[:8]}"

    response = await stranger.post(ADD_URL, work_post(title=title) | {"photo": _uploaded()})

    assert response.headers["Location"].startswith(LOGIN_URL)
    assert not await _works().filter(title=title).aexists()


def test_every_refusal_the_work_card_can_meet_is_named_in_the_owner_s_words() -> None:
    """A code missing from the table shows «Запись отклонена.» and is invisible without this check."""
    named = REFUSAL_MESSAGES.keys()

    assert set(WORK_REFUSALS) <= named
