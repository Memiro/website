from dataclasses import dataclass, field
from enum import StrEnum, auto

from memiro.entities.catalog.attribute.rate import Rate
from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId


class AttributeKind(StrEnum):
    """How a customer configures an attribute."""

    SELECT = auto()
    NUMBER = auto()


@dataclass
class AttributeValue(Entity):
    """A dictionary row of an attribute: "silver", "no frame", "cut-out".

    The row both describes the product and forms its price: the tariff lives
    here and nowhere else (ADR-0007).
    """

    id: AttributeValueId
    name: str
    rate: Rate
    scaled_by_shape: bool
    sort_order: int
    marks_absence: bool = False
    scaled_by_size_surcharge: bool = False

    def is_present(self) -> bool:
        """Tell whether this row names a feature the product actually has."""
        return not self.marks_absence


@dataclass
class Attribute(Entity):
    """A characteristic of a product, kept in the admin dictionary.

    Aggregate root; the dictionary rows are its children. Ownership of the
    set (``replace_values``) and the audit dates arrive with the admin write
    path — this slice only reads the dictionary.
    """

    id: AttributeId
    category_id: CategoryId
    name: str
    sort_order: int
    values: list[AttributeValue] = field(default_factory=list[AttributeValue])
    kind: AttributeKind = AttributeKind.SELECT
    parent_ids: tuple[AttributeId, ...] = ()
    is_customer_changeable: bool = True

    def __post_init__(self) -> None:
        """Hold dictionary shape invariants and detach parent identifiers."""
        if self.kind is AttributeKind.NUMBER and len(self.values) != 1:
            msg = f"Numeric attribute {self.id} needs exactly one tariff row"
            raise RuntimeError(msg)
        self.parent_ids = tuple(self.parent_ids)

    def value(self, value_id: AttributeValueId) -> AttributeValue | None:
        """Find a dictionary row of this attribute, or report that it is not one."""
        return next((value for value in self.values if value.id == value_id), None)
