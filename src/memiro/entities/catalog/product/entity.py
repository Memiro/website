from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId, ProductId, VariantId
from memiro.entities.common.measure import Dimensions
from memiro.entities.common.money import Money
from memiro.entities.errors.product import (
    DuplicateVariantError,
    InvalidVariantConfigurationError,
    InvalidVariantSortOrderError,
)


def _variant_key(variant: Variant) -> tuple[int, int, tuple[tuple[AttributeId, ConfiguredValue], ...]]:
    """Canonicalize rotation and override order for the duplicate invariant."""
    overrides = tuple(
        sorted(
            ((override.attribute_id, override.configured) for override in variant.overrides),
            key=lambda item: str(item[0]),
        )
    )
    return (
        variant.dimensions.long_side.value,
        variant.dimensions.short_side.value,
        overrides,
    )


def _variant_fingerprint(variant: Variant) -> UUID:
    """Build the stable database guard for the exact domain duplicate key."""
    long_side, short_side, overrides = _variant_key(variant)
    override_key = ";".join(f"{attribute_id}:{_configured_key(configured)}" for attribute_id, configured in overrides)
    return uuid5(NAMESPACE_URL, f"memiro/variant/{long_side}/{short_side}/{override_key}")


def _configured_key(configured: ConfiguredValue) -> str:
    """Give equal dictionary and numeric configurations equal canonical text."""
    if configured.value_id is not None:
        return f"value/{configured.value_id}"
    if configured.quantity is None:
        msg = "A variant fingerprint needs a complete override"
        raise RuntimeError(msg)
    return f"quantity/{format(configured.quantity.normalize(), 'f')}"


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
    configured: ConfiguredValue


@dataclass(frozen=True, slots=True)
class VariantData:
    """Owner-controlled fields of one precalculated product variant."""

    dimensions: Dimensions
    overrides: tuple[DeclaredValue, ...]
    sort_order: int


@dataclass
class Variant(Entity):
    """One ready configuration whose price was calculated by the domain service."""

    id: VariantId
    dimensions: Dimensions
    overrides: tuple[DeclaredValue, ...]
    price: Money
    sort_order: int
    fingerprint: UUID = field(init=False)

    def __post_init__(self) -> None:
        """Reject a child whose owner order cannot be represented."""
        if self.sort_order < 0:
            raise InvalidVariantSortOrderError
        attribute_ids = [override.attribute_id for override in self.overrides]
        if len(set(attribute_ids)) != len(attribute_ids):
            raise InvalidVariantConfigurationError(
                message="A variant can override an attribute only once",
            )
        if any(
            override.configured.value_id is None and override.configured.quantity is None for override in self.overrides
        ):
            raise InvalidVariantConfigurationError(
                message="A variant override must name a value or a quantity",
            )
        self.fingerprint = _variant_fingerprint(self)


@dataclass
class Product(Entity):
    """A made-to-order product with its declarations and precalculated variants.

    Aggregate root. Price is never assigned to a product from outside — it is
    derived from its precalculated variants.
    """

    id: ProductId
    category_id: CategoryId
    name: str
    slug: str
    is_published: bool
    declared_values: list[DeclaredValue] = field(default_factory=list[DeclaredValue])
    hides_calculated_price: bool = False
    price_from: Money | None = field(init=False, default=None)
    _variants: list[Variant] = field(default_factory=list[Variant], repr=False)

    @property
    def variants(self) -> tuple[Variant, ...]:
        """Return the precalculated variants without exposing the mutable collection."""
        return tuple(self._variants)

    def add_variant(self, data: VariantData, *, price: Money) -> Variant:
        """Add a priced variant and derive the product price from all variants."""
        variant = variant_factory(data, price=price)
        self._ensure_unique_variant(variant)
        self._variants.append(variant)
        self._settle_price_from()
        return variant

    def change_variant(self, variant: Variant, data: VariantData, *, price: Money) -> Variant:
        """Replace one loaded child and derive the product price again."""
        replacement = Variant(
            id=variant.id,
            dimensions=data.dimensions,
            overrides=data.overrides,
            price=price,
            sort_order=data.sort_order,
        )
        self._ensure_unique_variant(replacement, excluding=variant.id)
        index = self._variant_index(variant)
        self._variants[index] = replacement
        self._settle_price_from()
        return replacement

    def remove_variant(self, variant: Variant) -> None:
        """Remove one loaded child and derive the product price again."""
        self._variants.pop(self._variant_index(variant))
        self._settle_price_from()

    def duplicate_variant_with_size(
        self,
        variant: Variant,
        dimensions: Dimensions,
        *,
        price: Money,
    ) -> Variant:
        """Copy one loaded child to another size with a freshly calculated price."""
        self._variant_index(variant)
        duplicate = variant_factory(
            VariantData(
                dimensions=dimensions,
                overrides=variant.overrides,
                sort_order=variant.sort_order,
            ),
            price=price,
        )
        self._ensure_unique_variant(duplicate)
        self._variants.append(duplicate)
        self._settle_price_from()
        return duplicate

    def declared(self, attribute_id: AttributeId) -> DeclaredValue | None:
        """Return what the product declared on the attribute, if it declared anything."""
        return next(
            (declared for declared in self.declared_values if declared.attribute_id == attribute_id),
            None,
        )

    def variant(self, variant_id: VariantId) -> Variant | None:
        """Return a precalculated child by identifier, if it belongs to this product."""
        return next((variant for variant in self._variants if variant.id == variant_id), None)

    def _settle_price_from(self) -> None:
        """Derive the storefront seam from the children that own its truth."""
        self.price_from = min((variant.price for variant in self._variants), default=None)

    def _ensure_unique_variant(self, candidate: Variant, *, excluding: VariantId | None = None) -> None:
        """Refuse a second child describing the same physical configuration."""
        candidate_key = _variant_key(candidate)
        if any(variant.id != excluding and _variant_key(variant) == candidate_key for variant in self._variants):
            raise DuplicateVariantError

    def _variant_index(self, variant: Variant) -> int:
        """Locate a child already resolved by the application layer."""
        try:
            return next(index for index, current in enumerate(self._variants) if current.id == variant.id)
        except StopIteration:
            msg = f"Variant {variant.id} does not belong to product {self.id}"
            raise RuntimeError(msg) from None


def variant_factory(data: VariantData, *, price: Money) -> Variant:
    """Create a priced child with an unforgeable identifier."""
    return Variant(
        id=uuid4(),
        dimensions=data.dimensions,
        overrides=data.overrides,
        price=price,
        sort_order=data.sort_order,
    )
