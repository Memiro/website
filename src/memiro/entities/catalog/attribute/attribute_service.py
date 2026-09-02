"""Rules an attribute cannot check alone: dependence is read across the dictionary (§6.3c)."""

from collections.abc import Sequence

from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.common.identifiers import AttributeId, CategoryId
from memiro.entities.errors.attribute import InvalidAttributeParentError


def ensure_parents_are_usable(
    parent_ids: Sequence[AttributeId],
    *,
    attribute_id: AttributeId | None,
    category_id: CategoryId,
    dictionary: Sequence[Attribute],
) -> None:
    """Refuse a dependence that leaves the category, points at itself or closes a circle."""
    index = {attribute.id: attribute for attribute in dictionary}
    for parent_id in parent_ids:
        parent = index.get(parent_id)
        if parent is None or parent.category_id != category_id or parent_id == attribute_id:
            raise InvalidAttributeParentError
    if attribute_id is not None and _reaches(attribute_id, from_ids=parent_ids, index=index):
        raise InvalidAttributeParentError


def ensure_no_attribute_depends_on(attribute_id: AttributeId, *, dictionary: Sequence[Attribute]) -> None:
    """Refuse removing an attribute another one names as its parent."""
    if any(attribute_id in attribute.parent_ids for attribute in dictionary):
        raise InvalidAttributeParentError(
            message="An attribute another attribute depends on cannot be removed",
        )


def _reaches(
    attribute_id: AttributeId,
    *,
    from_ids: Sequence[AttributeId],
    index: dict[AttributeId, Attribute],
) -> bool:
    """Walk the dependence upwards and tell whether the attribute is its own ancestor."""
    seen: set[AttributeId] = set()
    frontier = list(from_ids)
    while frontier:
        current = frontier.pop()
        if current == attribute_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        ancestor = index.get(current)
        if ancestor is not None:
            frontier.extend(ancestor.parent_ids)
    return False
