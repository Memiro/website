"""What the landing card sends: the owner's form as the commands of the aggregate (ADR-0012)."""

from collections.abc import Mapping
from typing import Any

from dishka import AsyncContainer

from memiro.application.manage_landings import (
    ChangeLanding,
    ChangeLandingForm,
    CreatedLanding,
    CreateLanding,
    CreateLandingForm,
    RemoveLanding,
)
from memiro.entities.common.identifiers import LandingId
from memiro.presentation.django_admin.forms import NARROWING_FIELD
from memiro.presentation.django_admin.writes import send


def create_landing(card: Mapping[str, Any]) -> LandingId:
    """Send the card of a new page as the command that enters it into the storefront."""
    form = CreateLandingForm(category_id=card["category"].id, **_copy_fields(card))
    created: CreatedLanding = send(lambda scope: _create(scope, form))
    return created.id


def restate_landing(landing_id: LandingId, card: Mapping[str, Any]) -> None:
    """Send the card of a saved page: the copy and the narrowing are one command of one aggregate."""
    form = ChangeLandingForm(**_copy_fields(card))
    send(lambda scope: _change(scope, landing_id, form))


def remove_landing(landing_id: LandingId) -> None:
    """Send one page to the command that removes it with its narrowing."""
    send(lambda scope: _remove(scope, landing_id))


def _copy_fields(card: Mapping[str, Any]) -> dict[str, Any]:
    """Read the card in the words of the application form."""
    return {
        "slug": card["slug"],
        "title": card["title"],
        "heading": card["heading"],
        "description": card["description"],
        "text": card["text"],
        "is_published": card["is_published"],
        "sort_order": card["sort_order"],
        "conditions": [value.pk for value in card[NARROWING_FIELD]],
    }


async def _create(scope: AsyncContainer, form: CreateLandingForm) -> CreatedLanding:
    interactor = await scope.get(CreateLanding)
    return await interactor.execute(form)


async def _change(scope: AsyncContainer, landing_id: LandingId, form: ChangeLandingForm) -> None:
    interactor = await scope.get(ChangeLanding)
    await interactor.execute(landing_id, form)


async def _remove(scope: AsyncContainer, landing_id: LandingId) -> None:
    interactor = await scope.get(RemoveLanding)
    await interactor.execute(landing_id)
