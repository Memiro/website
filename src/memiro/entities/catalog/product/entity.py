from dataclasses import dataclass, field

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, ProductId


@dataclass
class DeclaredValue(Entity):
    """What the owner declared for the product on one attribute of its category.

    No identifier of its own: the set is replaced whole, so telling one row
    from another by id would buy nothing.
    """

    attribute_id: AttributeId
    value_id: AttributeValueId


@dataclass
class Product(Entity):
    """A made-to-order product: its declared values and (later) its variants.

    Aggregate root. Price is never assigned to a product from outside — it is
    derived from its precalculated variants, which arrive with their own
    slice.
    """

    id: ProductId
    name: str
    slug: str
    declared_values: list[DeclaredValue] = field(default_factory=list[DeclaredValue])

    def declared(self, attribute_id: AttributeId) -> DeclaredValue | None:
        """Return what the product declared on the attribute, if it declared anything."""
        return next(
            (declared for declared in self.declared_values if declared.attribute_id == attribute_id),
            None,
        )
