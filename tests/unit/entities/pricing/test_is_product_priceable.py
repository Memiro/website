from dataclasses import replace
from uuid import uuid4

import pytest
from hypothesis import given, settings

from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product
from memiro.entities.pricing.pricing_service import is_product_priceable
from tests.common.factory.catalog import (
    BACKLIGHT,
    CONTOUR,
    FRAME,
    MOUNT,
    NO_FRAME,
    RECTANGULAR,
    SHAPE,
    demo_attributes,
    demo_attributes_replacing,
    demo_backlight,
    demo_frame,
    demo_heating,
    demo_product,
    demo_product_with_value,
    demo_product_without,
    demo_shape,
)
from tests.unit.composite import complete_products, incomplete_products


def test_a_product_missing_an_applicable_declaration_is_not_priceable() -> None:
    """A root attribute without a product declaration makes the product not priceable."""
    product = demo_product_without(MOUNT)

    result = is_product_priceable(product, demo_attributes())

    assert not result


def test_an_absent_parent_makes_its_undeclared_child_inapplicable() -> None:
    """An absence-marked parent lets its undeclared dependent attribute stay inapplicable."""
    result = is_product_priceable(demo_product(), demo_attributes())

    assert result


def test_a_present_parent_makes_its_child_declaration_required() -> None:
    """A present parent makes an undeclared dependent attribute required for pricing."""
    product = demo_product_with_value(BACKLIGHT, CONTOUR)

    result = is_product_priceable(product, demo_attributes())

    assert not result


def test_a_product_without_a_paid_declaration_is_not_priceable() -> None:
    """A complete product made only of a free absence value is not priceable."""
    product = replace(
        demo_product(),
        declared_values=[
            DeclaredValue(
                attribute_id=FRAME,
                configured=ConfiguredValue(value_id=NO_FRAME, quantity=None),
            )
        ],
    )

    result = is_product_priceable(product, [demo_frame()])

    assert not result


def test_a_free_present_parent_still_makes_its_child_required() -> None:
    """A zero tariff does not make a present parent value mean absence."""
    backlight = demo_backlight()
    backlight = replace(
        backlight,
        values=[backlight.values[0], replace(backlight.values[1], marks_absence=False)],
    )
    attributes = demo_attributes_replacing(backlight)

    result = is_product_priceable(demo_product(), attributes)

    assert not result


def test_a_factor_without_a_money_line_does_not_make_a_product_priceable() -> None:
    """A shape factor alone cannot satisfy the paid-declaration rule."""
    product = replace(
        demo_product(),
        declared_values=[
            DeclaredValue(
                attribute_id=SHAPE,
                configured=ConfiguredValue(value_id=RECTANGULAR, quantity=None),
            )
        ],
    )

    result = is_product_priceable(product, [demo_shape()])

    assert not result


def test_attributes_of_another_category_do_not_make_a_product_incomplete() -> None:
    """Priceability considers only attributes belonging to the product category."""
    foreign = replace(demo_frame(), id=uuid4(), category_id=uuid4())

    result = is_product_priceable(demo_product(), [*demo_attributes(), foreign])

    assert result


def test_a_missing_parent_is_reported_as_a_dictionary_defect() -> None:
    """A missing parent raises an English RuntimeError instead of leaking a KeyError."""
    child = replace(demo_heating(), parent_ids=(uuid4(),))
    attributes = demo_attributes_replacing(child)

    with pytest.raises(
        RuntimeError,
        match=r"Parent attribute .* is missing or outside product category",
    ):
        is_product_priceable(demo_product(), attributes)


def test_a_parent_from_another_category_is_reported_as_a_dictionary_defect() -> None:
    """A foreign-category parent raises an English RuntimeError as corrupted dictionary state."""
    foreign_parent = replace(demo_backlight(), category_id=uuid4())
    attributes = demo_attributes_replacing(foreign_parent)

    with pytest.raises(
        RuntimeError,
        match=r"Parent attribute .* is missing or outside product category",
    ):
        is_product_priceable(demo_product(), attributes)


@settings(max_examples=25)
@given(product=complete_products())
def test_every_coherently_complete_product_is_priceable(product: Product) -> None:
    """A complete set stays priceable whether an absent dependency stays off or is filled."""
    result = is_product_priceable(product, demo_attributes())

    assert result


@settings(max_examples=25)
@given(product=incomplete_products())
def test_every_coherent_declaration_gap_makes_a_product_not_priceable(product: Product) -> None:
    """Missing any required root or newly applicable child always makes the product not priceable."""
    result = is_product_priceable(product, demo_attributes())

    assert not result
