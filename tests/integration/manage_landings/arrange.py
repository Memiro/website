"""Forms and readings the three landing scenarios share."""

from dishka import AsyncContainer

from memiro.application.common.gateway.landing import LandingGateway
from memiro.application.manage_landings import ChangeLandingForm, CreatedLanding, CreateLanding, CreateLandingForm
from memiro.entities.catalog.landing.entity import Landing
from memiro.entities.common.identifiers import LandingId
from tests.common.factory.catalog import CATEGORY, ROUND

LANDING_SLUG = "kruglye-zerkala"


def create_form(**overrides: object) -> CreateLandingForm:
    """Build the owner's card for the page that stands for round mirrors."""
    fields: dict[str, object] = {
        "category_id": CATEGORY,
        "slug": LANDING_SLUG,
        "title": "Круглые зеркала на заказ — memiro",
        "heading": "Круглые зеркала",
        "description": "Круглые зеркала по вашему диаметру.",
        "text": "Круг читается мягче прямоугольника.",  # noqa: RUF001
        "is_published": True,
        "sort_order": 1,
        "conditions": [ROUND],
    }
    return CreateLandingForm.model_validate(fields | overrides)


def change_form(**overrides: object) -> ChangeLandingForm:
    """Build the card of a saved page: the same fields without the category."""
    fields = create_form(**overrides).model_dump()
    del fields["category_id"]
    return ChangeLandingForm.model_validate(fields)


async def load_landing(container: AsyncContainer, landing_id: LandingId) -> Landing | None:
    """Read the whole page back in a fresh transaction after a command."""
    async with container() as request:
        gateway: LandingGateway = await request.get(LandingGateway)
        return await gateway.get(landing_id)


async def create_landing(container: AsyncContainer, form: CreateLandingForm) -> CreatedLanding:
    """Execute one creation in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(CreateLanding)
        return await interactor.execute(form)
