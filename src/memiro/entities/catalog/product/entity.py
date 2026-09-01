from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Self
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId, ProductId, VariantId
from memiro.entities.common.measure import Dimensions
from memiro.entities.common.money import Money
from memiro.entities.errors.product import (
    DuplicateVariantError,
    InvalidQuantityError,
    InvalidVariantConfigurationError,
    InvalidVariantSortOrderError,
)


def _variant_fingerprint(variant: Variant) -> UUID:
    """Build the stable database guard for the exact domain duplicate key."""
    long_side, short_side, overrides = variant.configuration_key()
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
        """Reject two simultaneous representations, and a consumption below zero."""
        if self.value_id is not None and self.quantity is not None:
            msg = "Configured value cannot name both a dictionary row and a quantity"
            raise RuntimeError(msg)
        # Zero is a declaration ("no cutouts"), below zero is not: it would
        # reach ``Rate.charge`` and leave as a 500 from ``Money`` — a refusal
        # the customer is owed as a 4xx instead.
        if self.quantity is not None and self.quantity < 0:
            raise InvalidQuantityError


@dataclass
class DeclaredValue(Entity):
    """What the owner declared for the product on one attribute of its category.

    No identifier of its own: the set is replaced whole, so telling one row
    from another by id would buy nothing.
    """

    attribute_id: AttributeId
    configured: ConfiguredValue


class VariantOverrides(tuple[DeclaredValue, ...]):
    """Immutable validated copies of a variant's value overrides."""

    __slots__ = ()

    def __new__(cls, values: Iterable[DeclaredValue] = ()) -> Self:
        """Copy children and preserve the eternal override invariants."""
        overrides = tuple(
            DeclaredValue(attribute_id=value.attribute_id, configured=value.configured) for value in values
        )
        attribute_ids = [override.attribute_id for override in overrides]
        if len(set(attribute_ids)) != len(attribute_ids):
            raise InvalidVariantConfigurationError(
                message="A variant can override an attribute only once",
            )
        if any(override.configured.value_id is None and override.configured.quantity is None for override in overrides):
            raise InvalidVariantConfigurationError(
                message="A variant override must name a value or a quantity",
            )
        return super().__new__(cls, overrides)


@dataclass(frozen=True, slots=True)
class VariantData:
    """Owner-controlled fields of one precalculated product variant."""

    dimensions: Dimensions
    overrides: tuple[DeclaredValue, ...]
    sort_order: int

    def __post_init__(self) -> None:
        """Validate the complete owner-controlled child shape."""
        object.__setattr__(self, "overrides", VariantOverrides(self.overrides))


@dataclass(init=False)
class Variant(Entity):
    """One ready configuration whose price was calculated by the domain service."""

    id: VariantId
    _dimensions: Dimensions
    _overrides: VariantOverrides
    _price: Money
    _sort_order: int
    _fingerprint: UUID = field(init=False)

    def __init__(
        self,
        id: VariantId,  # noqa: A002 - the domain field is named id by §6.1.
        *,
        dimensions: Dimensions,
        overrides: tuple[DeclaredValue, ...],
        price: Money,
        sort_order: int,
    ) -> None:
        """Keep child state writable only to the aggregate and the ORM."""
        self.id = id
        self._dimensions = dimensions
        self._overrides = VariantOverrides(overrides)
        self._price = price
        self._sort_order = sort_order
        self.__post_init__()

    @property
    def dimensions(self) -> Dimensions:
        """Return the immutable dimensions value object."""
        return self._dimensions

    @property
    def overrides(self) -> tuple[DeclaredValue, ...]:
        """Return copies so a caller cannot mutate the aggregate through a child."""
        return tuple(
            DeclaredValue(attribute_id=override.attribute_id, configured=override.configured)
            for override in self._overrides
        )

    @property
    def price(self) -> Money:
        """Return the system-calculated price."""
        return self._price

    @property
    def sort_order(self) -> int:
        """Return the order chosen by the owner."""
        return self._sort_order

    def __post_init__(self) -> None:
        """Reject a child whose owner order cannot be represented."""
        if self._sort_order < 0:
            raise InvalidVariantSortOrderError
        self._fingerprint = _variant_fingerprint(self)

    def ensure_stored_fingerprint(self) -> None:
        """Refuse persisted child state whose uniqueness guard is stale or corrupt."""
        expected = _variant_fingerprint(self)
        if self._fingerprint != expected:
            msg = f"Variant {self.id} has a corrupted fingerprint"
            raise RuntimeError(msg)

    def configuration_key(self) -> tuple[int, int, tuple[tuple[AttributeId, ConfiguredValue], ...]]:
        """Return the rotation- and order-independent duplicate identity."""
        overrides = tuple(
            sorted(
                ((override.attribute_id, override.configured) for override in self._overrides),
                key=lambda item: str(item[0]),
            )
        )
        return (
            self._dimensions.long_side.value,
            self._dimensions.short_side.value,
            overrides,
        )


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
    hides_calculated_price: bool = False
    _declared_values: list[DeclaredValue] = field(default_factory=list[DeclaredValue], repr=False)
    _price_from: Money | None = field(init=False, default=None, repr=False)
    _variants: list[Variant] = field(default_factory=list[Variant], repr=False)

    @property
    def price_from(self) -> Money | None:
        """Return the minimum child price derived by aggregate commands."""
        return self._price_from

    @property
    def declared_values(self) -> tuple[DeclaredValue, ...]:
        """Return what the owner declared without exposing the mutable collection."""
        return tuple(self._declared_values)

    def declare_values(self, values: Iterable[DeclaredValue]) -> None:
        """Replace what the owner declared for this product on the attributes of its category."""
        self._declared_values = list(values)

    @property
    def variants(self) -> tuple[Variant, ...]:
        """Return the precalculated variants without exposing the mutable collection."""
        return tuple(sorted(self._variants, key=lambda variant: (variant.sort_order, str(variant.id))))

    def add_variant(self, data: VariantData, *, price: Money) -> Variant:
        """Add a priced variant and derive the product price from all variants."""
        variant = variant_factory(self._canonical_variant_data(data), price=price)
        self._ensure_unique_variant(variant)
        self._variants.append(variant)
        self._settle_price_from()
        return variant

    def change_variant(self, variant: Variant, data: VariantData, *, price: Money) -> Variant:
        """Replace one loaded child and derive the product price again."""
        canonical = self._canonical_variant_data(data)
        replacement = Variant(
            variant.id,
            dimensions=canonical.dimensions,
            overrides=canonical.overrides,
            price=price,
            sort_order=canonical.sort_order,
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
        self._price_from = min((variant.price for variant in self._variants), default=None)

    def _canonical_variant_data(self, data: VariantData) -> VariantData:
        """Drop overrides that repeat the product's own configured value."""
        overrides: list[DeclaredValue] = []
        for override in data.overrides:
            declared = self.declared(override.attribute_id)
            if declared is None or declared.configured != override.configured:
                overrides.append(override)
        return VariantData(
            dimensions=data.dimensions,
            overrides=tuple(overrides),
            sort_order=data.sort_order,
        )

    def _ensure_unique_variant(self, candidate: Variant, *, excluding: VariantId | None = None) -> None:
        """Refuse a second child describing the same physical configuration."""
        candidate_key = candidate.configuration_key()
        if any(variant.id != excluding and variant.configuration_key() == candidate_key for variant in self._variants):
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
        uuid4(),
        dimensions=data.dimensions,
        overrides=data.overrides,
        price=price,
        sort_order=data.sort_order,
    )
