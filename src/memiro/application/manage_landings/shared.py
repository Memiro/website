import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.landing import LandingGateway
from memiro.application.common.input_limits import (
    MAX_LANDING_CONDITIONS,
    MAX_LANDING_TEXT_LENGTH,
    MAX_META_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
)
from memiro.application.errors.catalog import LandingNotFoundError, LandingSlugTakenError
from memiro.entities.catalog.landing.entity import Landing, LandingCondition
from memiro.entities.catalog.landing.landing_service import ensure_the_narrowing_is_buildable
from memiro.entities.common.identifiers import AttributeValueId, CategoryId, LandingId
from memiro.entities.common.slug import MAX_SLUG_LENGTH
from memiro.entities.errors.landing import InvalidLandingNarrowingError
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)

# Either the address the owner typed — lowercase latin words joined by single
# hyphens — or nothing, which the domain fills in from the heading.
SLUG_PATTERN = r"^$|^[a-z0-9]+(?:-[a-z0-9]+)*$"


class LandingCopyForm(BaseModel):
    """What the owner writes on a landing, as his card submits it."""

    slug: str = Field(default="", max_length=MAX_SLUG_LENGTH, pattern=SLUG_PATTERN)
    title: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    heading: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    description: str = Field(default="", max_length=MAX_META_DESCRIPTION_LENGTH)
    text: str = Field(default="", max_length=MAX_LANDING_TEXT_LENGTH)
    is_published: bool = False
    sort_order: int = Field(default=0, ge=0)
    # The values are named alone: which attribute each belongs to is the
    # dictionary's answer, not the card's, and a card that named both could
    # narrow by a pair the dictionary never had.
    conditions: list[AttributeValueId] = Field(
        default_factory=list[AttributeValueId],
        max_length=MAX_LANDING_CONDITIONS,
    )


async def narrowing_of(
    gateway: AttributeGateway,
    value_ids: list[AttributeValueId],
    *,
    category_id: CategoryId,
) -> tuple[LandingCondition, ...]:
    """Resolve the values the owner ticked into conditions the sidebar could build."""
    dictionary = await gateway.list_with_values()
    owner = {value.id: attribute.id for attribute in dictionary for value in attribute.values}
    for value_id in value_ids:
        if value_id not in owner:
            logger.warning("A landing named a value the dictionary does not hold", value_id=value_id)
            raise InvalidLandingNarrowingError(message="A landing narrows by values the dictionary holds")
    conditions = tuple(LandingCondition(attribute_id=owner[value_id], value_id=value_id) for value_id in value_ids)
    ensure_the_narrowing_is_buildable(conditions, category_id=category_id, dictionary=dictionary)
    return conditions


async def loaded_for_update(gateway: LandingGateway, landing_id: LandingId, *, command: str) -> Landing:
    """Load one landing under its lock, refusing an identifier nobody issued."""
    landing = await gateway.get(landing_id, for_update=True)
    if landing is None:
        logger.warning("A command named an unknown landing", landing_id=landing_id, command=command)
        raise LandingNotFoundError
    return landing


async def ensure_the_address_is_free(
    gateway: LandingGateway,
    slug: str,
    *,
    except_landing: LandingId | None,
) -> None:
    """Refuse an address another landing already answers on."""
    holder = await gateway.slug_owner(slug)
    if holder is not None and holder != except_landing:
        logger.warning("A landing address is already taken", slug=slug)
        raise LandingSlugTakenError
