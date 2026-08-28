from dataclasses import dataclass, field
from decimal import Decimal

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId, ProductId


@dataclass(frozen=True, slots=True)
class ConfiguredValue:
    """One configured attribute, expressed as either a dictionary row or a quantity."""

    value_id: AttributeValueId | None
    quantity: Decimal | None

    def __post_init__(self) -> None:
        """Reject two simultaneous representations as a programmer defect."""
        if self.value_id is not None and self.quantity is not None:
            msg = "Configured value cannot name both a dictionary row and a quantity"
            raise RuntimeError(msg)


@dataclass
class DeclaredValue(Entity):
    """What the owner declared for the product on one attribute of its category.

    No identifier of its own: the set is replaced whole, so telling one row
    from another by id would buy nothing.
    """

    attribute_id: AttributeId
    value_id: AttributeValueId | None
    quantity: Decimal | None = None

    def __post_init__(self) -> None:
        """Reject two simultaneous representations while keeping an unfinished declaration legal."""
        if self.value_id is not None and self.quantity is not None:
            msg = "Declared value cannot name both a dictionary row and a quantity"
            raise RuntimeError(msg)


@dataclass
class Product(Entity):
    """A made-to-order product: its declared values and (later) its variants.

    Aggregate root. Price is never assigned to a product from outside — it is
    derived from its precalculated variants, which arrive with their own
    slice.
    """

    id: ProductId
    category_id: CategoryId
    name: str
    slug: str
    is_published: bool
    declared_values: list[DeclaredValue] = field(default_factory=list[DeclaredValue])
    hides_calculated_price: bool = False

    def declared(self, attribute_id: AttributeId) -> DeclaredValue | None:
        """Return what the product declared on the attribute, if it declared anything."""
        return next(
            (declared for declared in self.declared_values if declared.attribute_id == attribute_id),
            None,
        )
