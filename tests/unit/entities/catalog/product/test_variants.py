from decimal import Decimal

import pytest

from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.product.entity import DeclaredValue, Variant, VariantData
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.product import (
    DuplicateVariantError,
    InvalidVariantConfigurationError,
    InvalidVariantSortOrderError,
)
from tests.common.factory.catalog import BLADE, FRAME, GRAPHITE, NO_FRAME, SILVER, demo_product

TWO_VARIANTS = 2


def _variant_data(
    *,
    width_mm: int,
    height_mm: int,
    overrides: tuple[DeclaredValue, ...] = (),
    sort_order: int = 0,
) -> VariantData:
    """Build a variant with no overrides where their values do not matter."""
    return VariantData(
        dimensions=Dimensions(
            width=Millimeters(value=width_mm),
            height=Millimeters(value=height_mm),
        ),
        overrides=overrides,
        sort_order=sort_order,
    )


def test_a_product_derives_its_price_from_the_cheapest_variant() -> None:
    """A product's price is the minimum price among its variants."""
    product = demo_product()
    product.add_variant(
        _variant_data(width_mm=1200, height_mm=800),
        price=Money(amount=Decimal(9000)),
    )

    product.add_variant(
        _variant_data(width_mm=600, height_mm=400),
        price=Money(amount=Decimal(2000)),
    )

    assert product.price_from == Money(amount=Decimal(2000))


def test_a_product_does_not_let_its_derived_price_be_assigned() -> None:
    """The derived price has no external assignment path."""
    product = demo_product()

    with pytest.raises(AttributeError):
        product.price_from = Money(amount=Decimal(1))  # type: ignore[misc]

    assert product.price_from is None


def test_a_product_does_not_expose_mutable_variant_state() -> None:
    """A child price can change only through a Product command."""
    product = demo_product()
    variant = product.add_variant(
        _variant_data(width_mm=600, height_mm=400),
        price=Money(amount=Decimal(2000)),
    )

    with pytest.raises(AttributeError):
        variant.price = Money(amount=Decimal(1))  # type: ignore[misc]

    assert product.price_from == Money(amount=Decimal(2000))


def test_a_product_copies_an_override_before_accepting_it() -> None:
    """A caller cannot stale a child fingerprint through an accepted input object."""
    product = demo_product()
    override = DeclaredValue(
        attribute_id=BLADE,
        chosen=ChosenValue(value_id=GRAPHITE, quantity=None),
    )
    variant = product.add_variant(
        _variant_data(width_mm=600, height_mm=400, overrides=(override,)),
        price=Money(amount=Decimal(3000)),
    )

    override.chosen = ChosenValue(value_id=SILVER, quantity=None)

    assert variant.overrides == (
        DeclaredValue(
            attribute_id=BLADE,
            chosen=ChosenValue(value_id=GRAPHITE, quantity=None),
        ),
    )


def test_changing_the_cheapest_variant_rederives_the_product_price() -> None:
    """Changing the cheapest variant can make another variant the product price."""
    product = demo_product()
    cheapest = product.add_variant(
        _variant_data(width_mm=600, height_mm=400),
        price=Money(amount=Decimal(2000)),
    )
    product.add_variant(
        _variant_data(width_mm=1200, height_mm=800),
        price=Money(amount=Decimal(9000)),
    )

    product.change_variant(
        cheapest,
        _variant_data(width_mm=1400, height_mm=900),
        price=Money(amount=Decimal(12000)),
    )

    assert product.price_from == Money(amount=Decimal(9000))


def test_removing_the_last_variant_leaves_a_product_without_a_price() -> None:
    """A product without variants has no placeholder price."""
    product = demo_product()
    variant = product.add_variant(
        _variant_data(width_mm=600, height_mm=400),
        price=Money(amount=Decimal(2000)),
    )

    product.remove_variant(variant)

    assert product.price_from is None


def test_a_duplicated_variant_keeps_everything_but_its_size_and_price() -> None:
    """Duplicating by size preserves overrides and owner order but recalculates price."""
    product = demo_product()
    override = DeclaredValue(
        attribute_id=FRAME,
        chosen=ChosenValue(value_id=NO_FRAME, quantity=None),
    )
    source = product.add_variant(
        _variant_data(width_mm=600, height_mm=400, overrides=(override,), sort_order=7),
        price=Money(amount=Decimal(2000)),
    )
    new_dimensions = Dimensions(
        width=Millimeters(value=1200),
        height=Millimeters(value=800),
    )

    duplicate = product.duplicate_variant_with_size(
        source,
        new_dimensions,
        price=Money(amount=Decimal(9000)),
    )

    assert duplicate.id != source.id
    assert duplicate == Variant(
        duplicate.id,
        dimensions=new_dimensions,
        overrides=source.overrides,
        price=Money(amount=Decimal(9000)),
        sort_order=source.sort_order,
    )


def test_a_product_rejects_a_rotated_duplicate_with_reordered_overrides() -> None:
    """The same rotated size and overrides are rejected with DUPLICATE_VARIANT."""
    product = demo_product()
    blade = DeclaredValue(
        attribute_id=BLADE,
        chosen=ChosenValue(value_id=SILVER, quantity=None),
    )
    frame = DeclaredValue(
        attribute_id=FRAME,
        chosen=ChosenValue(value_id=NO_FRAME, quantity=None),
    )
    product.add_variant(
        _variant_data(width_mm=600, height_mm=400, overrides=(blade, frame)),
        price=Money(amount=Decimal(2000)),
    )
    variants_before = product.variants

    with pytest.raises(DuplicateVariantError, match="same size and configured values"):
        product.add_variant(
            _variant_data(width_mm=400, height_mm=600, overrides=(frame, blade)),
            price=Money(amount=Decimal(2000)),
        )

    assert product.variants == variants_before
    assert product.price_from == Money(amount=Decimal(2000))


def test_a_product_rejects_a_duplicate_disguised_as_a_default_override() -> None:
    """A no-op override is rejected as the same effective DUPLICATE_VARIANT."""
    product = demo_product()
    default_blade = DeclaredValue(
        attribute_id=BLADE,
        chosen=ChosenValue(value_id=SILVER, quantity=None),
    )
    product.add_variant(
        _variant_data(width_mm=600, height_mm=400),
        price=Money(amount=Decimal(2000)),
    )

    with pytest.raises(DuplicateVariantError, match="same size and configured values"):
        product.add_variant(
            _variant_data(width_mm=600, height_mm=400, overrides=(default_blade,)),
            price=Money(amount=Decimal(2000)),
        )

    assert len(product.variants) == 1


def test_a_product_allows_one_size_with_different_overrides() -> None:
    """Different override sets describe different variants at the same size."""
    product = demo_product()
    blade = DeclaredValue(
        attribute_id=BLADE,
        chosen=ChosenValue(value_id=GRAPHITE, quantity=None),
    )
    product.add_variant(
        _variant_data(width_mm=600, height_mm=400),
        price=Money(amount=Decimal(2000)),
    )

    product.add_variant(
        _variant_data(width_mm=600, height_mm=400, overrides=(blade,)),
        price=Money(amount=Decimal(3000)),
    )

    assert len(product.variants) == TWO_VARIANTS


def test_a_product_exposes_variants_in_the_owner_order() -> None:
    """The lowest owner order is first even before the aggregate is reloaded."""
    product = demo_product()
    later = product.add_variant(
        _variant_data(width_mm=600, height_mm=400, sort_order=2),
        price=Money(amount=Decimal(2000)),
    )

    earlier = product.add_variant(
        _variant_data(width_mm=1200, height_mm=800, sort_order=1),
        price=Money(amount=Decimal(9000)),
    )

    assert product.variants == (earlier, later)


def test_changing_a_variant_cannot_duplicate_its_neighbour() -> None:
    """A conflicting change is rejected with DUPLICATE_VARIANT and changes no state."""
    product = demo_product()
    product.add_variant(
        _variant_data(width_mm=600, height_mm=400),
        price=Money(amount=Decimal(2000)),
    )
    changed = product.add_variant(
        _variant_data(width_mm=1200, height_mm=800),
        price=Money(amount=Decimal(9000)),
    )
    variants_before = product.variants

    with pytest.raises(DuplicateVariantError, match="same size and configured values"):
        product.change_variant(
            changed,
            _variant_data(width_mm=400, height_mm=600),
            price=Money(amount=Decimal(2000)),
        )

    assert product.variants == variants_before
    assert product.price_from == Money(amount=Decimal(2000))


def test_duplicating_to_an_existing_size_changes_nothing() -> None:
    """A conflicting duplicate is rejected with DUPLICATE_VARIANT and changes no state."""
    product = demo_product()
    existing = product.add_variant(
        _variant_data(width_mm=600, height_mm=400),
        price=Money(amount=Decimal(2000)),
    )
    source = product.add_variant(
        _variant_data(width_mm=1200, height_mm=800),
        price=Money(amount=Decimal(9000)),
    )
    variants_before = product.variants

    with pytest.raises(DuplicateVariantError, match="same size and configured values"):
        product.duplicate_variant_with_size(
            source,
            Dimensions(width=existing.dimensions.height, height=existing.dimensions.width),
            price=Money(amount=Decimal(2000)),
        )

    assert product.variants == variants_before
    assert product.price_from == Money(amount=Decimal(2000))


def test_a_variant_rejects_a_negative_owner_order() -> None:
    """A negative owner order is rejected with INVALID_VARIANT_SORT_ORDER."""
    product = demo_product()

    with pytest.raises(InvalidVariantSortOrderError, match="cannot be negative"):
        product.add_variant(
            _variant_data(width_mm=600, height_mm=400, sort_order=-1),
            price=Money(amount=Decimal(2000)),
        )

    assert product.variants == ()
    assert product.price_from is None


def test_a_variant_rejects_two_overrides_of_one_attribute() -> None:
    """Two overrides of one attribute are rejected with INVALID_VARIANT_CONFIGURATION."""
    product = demo_product()
    silver = DeclaredValue(
        attribute_id=BLADE,
        chosen=ChosenValue(value_id=SILVER, quantity=None),
    )

    with pytest.raises(InvalidVariantConfigurationError, match="only once"):
        product.add_variant(
            _variant_data(width_mm=600, height_mm=400, overrides=(silver, silver)),
            price=Money(amount=Decimal(2000)),
        )

    assert product.variants == ()
    assert product.price_from is None


def test_a_variant_rejects_an_unfinished_override() -> None:
    """An unfinished override is rejected with INVALID_VARIANT_CONFIGURATION."""
    product = demo_product()
    unfinished = DeclaredValue(
        attribute_id=BLADE,
        chosen=ChosenValue(value_id=None, quantity=None),
    )

    with pytest.raises(InvalidVariantConfigurationError, match="must name"):
        product.add_variant(
            _variant_data(width_mm=600, height_mm=400, overrides=(unfinished,)),
            price=Money(amount=Decimal(2000)),
        )

    assert product.variants == ()
    assert product.price_from is None
