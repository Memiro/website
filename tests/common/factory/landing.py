"""The landing every test of the write path arranges with."""

from memiro.entities.catalog.landing.entity import (
    ChangeLandingData,
    CreateLandingData,
    Landing,
    LandingCondition,
    landing_factory,
)
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from tests.clock import CLOCK
from tests.common.factory.catalog import CATEGORY, ROUND, SHAPE

LANDING_SLUG = "kruglye-zerkala"


def demo_landing_data(**overrides: object) -> CreateLandingData:
    """Build the owner's card for the landing that stands for round mirrors."""
    fields: dict[str, object] = {
        "category_id": CATEGORY,
        "slug": LANDING_SLUG,
        "title": "Круглые зеркала на заказ — memiro",
        "heading": "Круглые зеркала",
        "description": "Круглые зеркала по вашему диаметру.",
        "text": "Круг читается мягче прямоугольника.",  # noqa: RUF001
        "is_published": True,
        "sort_order": 1,
        "conditions": (demo_condition(),),
    }
    return CreateLandingData(**(fields | overrides))  # type: ignore[arg-type]  # the overrides are the test's own fields


def demo_landing_copy(**overrides: object) -> ChangeLandingData:
    """Build what the owner restates on a saved page: everything but the category it narrows."""
    data = demo_landing_data(**overrides)
    return ChangeLandingData(
        slug=data.slug,
        title=data.title,
        heading=data.heading,
        description=data.description,
        text=data.text,
        is_published=data.is_published,
        sort_order=data.sort_order,
    )


def demo_condition(
    attribute_id: AttributeId = SHAPE,
    value_id: AttributeValueId = ROUND,
) -> LandingCondition:
    """Build one condition of the demo narrowing."""
    return LandingCondition(attribute_id=attribute_id, value_id=value_id)


def demo_landing(**overrides: object) -> Landing:
    """Build the demo landing already narrowed to round mirrors."""
    return landing_factory(demo_landing_data(**overrides), clock=CLOCK)
