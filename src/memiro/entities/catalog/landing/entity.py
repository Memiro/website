from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId, LandingId
from memiro.entities.common.slug import slugify
from memiro.entities.errors.landing import InvalidLandingNarrowingError, InvalidLandingSlugError
from memiro_common.clock import Clock

# A landing stands for one or two questions about a mirror ("round", "in a
# frame"), never for a shopping session: more of them is the faceted page
# ADR-0003 keeps out of the index.
MAX_LANDING_ATTRIBUTES = 2


@dataclass
class LandingCondition(Entity):
    """One dictionary value a landing narrows its category by.

    No identifier of its own: the set is replaced whole, and the value it
    names is what tells one condition from another.
    """

    attribute_id: AttributeId
    value_id: AttributeValueId


@dataclass(frozen=True, slots=True)
class LandingCopy:
    """What the owner writes on a landing: its address and the words on it."""

    slug: str
    title: str
    heading: str
    description: str
    text: str
    is_published: bool
    sort_order: int


@dataclass(frozen=True, slots=True)
class CreateLandingData(LandingCopy):
    """Owner-controlled fields of the landing being created."""

    category_id: CategoryId


def settled_slug(slug: str, heading: str) -> str:
    """Take the address the owner typed, or derive one from the heading he wrote."""
    settled = slug or slugify(heading)
    if not settled:
        raise InvalidLandingSlugError
    return settled


@dataclass
class Landing(Entity):
    """An indexable page: one category narrowed by the values the owner wrote down.

    Aggregate root; the conditions are its children, and the narrowing is
    replaced whole by ``narrow_by`` rather than edited row by row.
    """

    id: LandingId
    category_id: CategoryId
    slug: str
    title: str
    heading: str
    description: str
    text: str
    is_published: bool
    sort_order: int
    _conditions: list[LandingCondition] = field(default_factory=list[LandingCondition], repr=False)
    created_at: datetime = field(kw_only=True)
    updated_at: datetime = field(kw_only=True)

    @property
    def conditions(self) -> tuple[LandingCondition, ...]:
        """Return the narrowing without exposing the mutable collection."""
        return tuple(self._conditions)

    @property
    def narrowing_attribute_ids(self) -> tuple[AttributeId, ...]:
        """List the attributes the page narrows by, each once, in the order they were written."""
        return tuple(dict.fromkeys(condition.attribute_id for condition in self._conditions))

    def change(self, data: LandingCopy, *, clock: Clock) -> None:
        """Restate what the owner writes on the page; the category it narrows is not his to move."""
        self.slug = settled_slug(data.slug, data.heading)
        self.title = data.title
        self.heading = data.heading
        self.description = data.description
        self.text = data.text
        self.is_published = data.is_published
        self.sort_order = data.sort_order
        self.updated_at = clock.now()

    def narrow_by(self, conditions: Iterable[LandingCondition], *, clock: Clock) -> None:
        """Replace the whole narrowing, holding what a landing may stand for."""
        replacement = [
            LandingCondition(attribute_id=condition.attribute_id, value_id=condition.value_id)
            for condition in conditions
        ]
        _ensure_the_page_stands_for_something(replacement)
        self._conditions = replacement
        self.updated_at = clock.now()


def landing_factory(data: CreateLandingData, *, clock: Clock) -> Landing:
    """Create a landing with an unforgeable identifier; both dates come from one reading of the clock."""
    now = clock.now()
    return Landing(
        id=uuid4(),
        category_id=data.category_id,
        slug=settled_slug(data.slug, data.heading),
        title=data.title,
        heading=data.heading,
        description=data.description,
        text=data.text,
        is_published=data.is_published,
        sort_order=data.sort_order,
        created_at=now,
        updated_at=now,
    )


def _ensure_the_page_stands_for_something(conditions: list[LandingCondition]) -> None:
    """Refuse a narrowing that is empty, repeated or wider than a landing may be."""
    if not conditions:
        raise InvalidLandingNarrowingError(message="A landing narrows its category by at least one value")
    value_ids = [condition.value_id for condition in conditions]
    if len(set(value_ids)) != len(value_ids):
        raise InvalidLandingNarrowingError(message="A landing names each value once")
    attribute_ids = {condition.attribute_id for condition in conditions}
    if len(attribute_ids) > MAX_LANDING_ATTRIBUTES:
        raise InvalidLandingNarrowingError(
            message=f"A landing narrows by at most {MAX_LANDING_ATTRIBUTES} attributes",
        )
