"""What the work card sends: the owner's form as the commands of the gallery (ADR-0012)."""

from collections.abc import Mapping
from typing import Any

from dishka import AsyncContainer
from django.core.files.uploadedfile import UploadedFile

from memiro.application.manage_works import (
    ChangeWork,
    ChangeWorkForm,
    CreatedWork,
    CreateWork,
    CreateWorkForm,
    PhotoForm,
    RemoveWork,
)
from memiro.entities.common.identifiers import WorkId
from memiro.presentation.django_admin.forms import PHOTO_FIELD
from memiro.presentation.django_admin.writes import send


def create_work(card: Mapping[str, Any]) -> WorkId:
    """Send the card of a new work as the command that enters it into the gallery."""
    photo = _photo(card)
    if photo is None:
        # The card of a new work makes the file field required, so a card
        # without one is a defect of the form, not an answer to the owner.
        msg = "The card of a new work reached the gallery without a photograph"
        raise RuntimeError(msg)
    form = CreateWorkForm(photo=photo, **_copy_fields(card))
    created: CreatedWork = send(lambda scope: _create(scope, form))
    return created.id


def restate_work(work_id: WorkId, card: Mapping[str, Any]) -> None:
    """Send the card of a saved work: an empty file field keeps the photograph it stands on."""
    form = ChangeWorkForm(photo=_photo(card), **_copy_fields(card))
    send(lambda scope: _change(scope, work_id, form))


def remove_work(work_id: WorkId) -> None:
    """Send one work to the command that takes it and its photograph out of the gallery."""
    send(lambda scope: _remove(scope, work_id))


def _copy_fields(card: Mapping[str, Any]) -> dict[str, Any]:
    """Read the card in the words of the application form."""
    product = card["product"]
    return {
        "product_id": None if product is None else product.pk,
        "title": card["title"],
        "description": card["description"],
        "is_published": card["is_published"],
        "sort_order": card["sort_order"],
    }


def _photo(card: Mapping[str, Any]) -> PhotoForm | None:
    """Read the file the owner picked, if he picked one at all."""
    photo: UploadedFile[Any] | None = card.get(PHOTO_FIELD)
    if photo is None:
        return None
    return PhotoForm(filename=photo.name or "", content=photo.read())


async def _create(scope: AsyncContainer, form: CreateWorkForm) -> CreatedWork:
    interactor = await scope.get(CreateWork)
    return await interactor.execute(form)


async def _change(scope: AsyncContainer, work_id: WorkId, form: ChangeWorkForm) -> None:
    interactor = await scope.get(ChangeWork)
    await interactor.execute(work_id, form)


async def _remove(scope: AsyncContainer, work_id: WorkId) -> None:
    interactor = await scope.get(RemoveWork)
    await interactor.execute(work_id)
