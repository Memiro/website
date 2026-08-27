from dataclasses import dataclass, field

from memiro.entities.catalog.attribute.rate import Rate
from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import AttributeId, AttributeValueId


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


@dataclass
class Attribute(Entity):
    """A characteristic of a product, kept in the admin dictionary.

    Aggregate root; the dictionary rows are its children. Ownership of the
    set (``replace_values``) and the audit dates arrive with the admin write
    path — this slice only reads the dictionary.
    """

    id: AttributeId
    name: str
    sort_order: int
    values: list[AttributeValue] = field(default_factory=list[AttributeValue])

    def value(self, value_id: AttributeValueId) -> AttributeValue | None:
        """Find a dictionary row of this attribute, or report that it is not one."""
        return next((value for value in self.values if value.id == value_id), None)
