"""Rules a landing cannot check alone: its narrowing is read against the dictionary (§6.3c)."""

from collections.abc import Sequence

from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind
from memiro.entities.catalog.landing.entity import LandingCondition
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId
from memiro.entities.errors.landing import InvalidLandingNarrowingError


def ensure_the_narrowing_is_buildable(
    conditions: Sequence[LandingCondition],
    *,
    category_id: CategoryId,
    dictionary: Sequence[Attribute],
) -> None:
    """Refuse a narrowing the sidebar could not build, or one that is the whole category again."""
    index = {attribute.id: attribute for attribute in dictionary}
    chosen: dict[AttributeId, set[AttributeValueId]] = {}
    for condition in conditions:
        attribute = index.get(condition.attribute_id)
        # The landing has no narrowing of its own: what the sidebar drops —
        # another category, a typed attribute, a switched-off one, a value of
        # someone else — would leave the page showing the whole category
        # under a narrowing heading (ADR-0003).
        if (
            attribute is None
            or attribute.category_id != category_id
            or attribute.kind is not AttributeKind.SELECT
            or not attribute.is_filterable
            or all(value.id != condition.value_id for value in attribute.values)
        ):
            raise InvalidLandingNarrowingError(
                message="A landing narrows by the filterable values of its own category",
            )
        chosen.setdefault(attribute.id, set()).add(condition.value_id)
    for attribute_id, value_ids in chosen.items():
        attribute = index[attribute_id]
        if len(value_ids) == len(attribute.values):
            raise InvalidLandingNarrowingError(
                message=f"Every value of «{attribute.name}» is the category itself, not a landing",
            )
