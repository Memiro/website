from decimal import Decimal

from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.product.entity import DeclaredValue
from memiro.entities.common.identifiers import ProductId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.inquiry.entity import ConfigurationValue, InquiryConfiguration, InquiryItemData
from memiro.entities.inquiry.inquiry_service import inquiry_configuration, inquiry_item_snapshot
from memiro.entities.pricing.quotation import PricingVerdict, Quotation
from tests.common.factory.catalog import (
    BACKLIGHT,
    BLADE,
    CONTOUR,
    CUTOUTS,
    GRAPHITE,
    HEATING,
    NO_HEATING,
    demo_attributes,
    demo_cutouts,
    demo_numeric_product,
    demo_product,
    product_with_added_declaration,
)

_MIRROR = demo_product()
_PRODUCT: ProductId = _MIRROR.id
_PRICE = Money(amount=Decimal(8820))
_DIMENSIONS = Dimensions(width=Millimeters(value=800), height=Millimeters(value=600))
_CONFIGURATION = InquiryConfiguration(dimensions=_DIMENSIONS, values=())

# The canonical mirror as the manager reads it: every declared value by name,
# in the owner's order of the dictionary.
_BLADE = ConfigurationValue(attribute_name="Тип полотна", value_name="Серебро", quantity=None)  # noqa: RUF001
_SHAPE = ConfigurationValue(attribute_name="Форма", value_name="Прямоугольное", quantity=None)
_FRAME = ConfigurationValue(attribute_name="Рама", value_name="Алюминий", quantity=None)
_NO_BACKLIGHT = ConfigurationValue(attribute_name="Подсветка", value_name="Без подсветки", quantity=None)
_MOUNT = ConfigurationValue(attribute_name="Крепление", value_name="С креплением", quantity=None)  # noqa: RUF001
_CONTOUR = ConfigurationValue(attribute_name="Подсветка", value_name="Контурная", quantity=None)


def _snapshot(
    verdict: PricingVerdict,
    calculated_price: Money | None,
    configuration: InquiryConfiguration | None,
) -> InquiryItemData:
    """Build one item snapshot straight from the combination under test."""
    return InquiryItemData(
        product_id=_PRODUCT,
        product_name="Зеркало в раме",
        price_from=None,
        configuration=configuration,
        calculated_price=calculated_price,
        verdict=verdict,
        wish="",
    )


def test_a_snapshot_takes_its_price_and_verdict_from_the_calculation() -> None:
    """The snapshot is built from the quotation, never from what the browser sent."""
    snapshot = inquiry_item_snapshot(
        product=_MIRROR,
        configuration=_CONFIGURATION,
        quotation=Quotation(verdict=PricingVerdict.PRICED, total=_PRICE, breakdown=()),
        wish="",
    )

    assert snapshot == _snapshot(PricingVerdict.PRICED, _PRICE, _CONFIGURATION)


def test_a_snapshot_of_a_not_priceable_product_drops_the_configuration() -> None:
    """The verdict decides whether a configuration is kept, and it decides in the domain."""
    snapshot = inquiry_item_snapshot(
        product=_MIRROR,
        configuration=_CONFIGURATION,
        quotation=Quotation(verdict=PricingVerdict.NOT_PRICEABLE, total=None, breakdown=()),
        wish="",
    )

    assert snapshot == _snapshot(PricingVerdict.NOT_PRICEABLE, None, None)


def test_a_configuration_names_every_declared_value_of_the_product_in_dictionary_order() -> None:
    """A customer who chose nothing still sends the manager the whole specification (rule 21)."""
    configuration = inquiry_configuration(
        product=_MIRROR,
        attributes=demo_attributes(),
        dimensions=_DIMENSIONS,
        selections={},
    )

    assert configuration == InquiryConfiguration(
        dimensions=_DIMENSIONS,
        values=(_BLADE, _SHAPE, _FRAME, _NO_BACKLIGHT, _MOUNT),
    )


def test_a_customer_choice_replaces_the_declared_value_in_the_configuration() -> None:
    """The chosen blade stands where the declared one stood, and nothing tells the two apart."""
    configuration = inquiry_configuration(
        product=_MIRROR,
        attributes=demo_attributes(),
        dimensions=_DIMENSIONS,
        selections={BLADE: ChosenValue(value_id=GRAPHITE, quantity=None)},
    )

    assert configuration.values == (
        ConfigurationValue(attribute_name="Тип полотна", value_name="Графит", quantity=None),
        _SHAPE,
        _FRAME,
        _NO_BACKLIGHT,
        _MOUNT,
    )


def test_a_dependent_attribute_the_product_never_declared_stays_out_of_the_configuration() -> None:
    """Heating opened by a backlight choice has no value to name, so the specification does not invent one."""
    configuration = inquiry_configuration(
        product=_MIRROR,
        attributes=demo_attributes(),
        dimensions=_DIMENSIONS,
        selections={BACKLIGHT: ChosenValue(value_id=CONTOUR, quantity=None)},
    )

    assert configuration.values == (_BLADE, _SHAPE, _FRAME, _CONTOUR, _MOUNT)


def test_a_dependent_attribute_enters_the_configuration_once_its_parent_is_present() -> None:
    """A declared heating is named by the specification only when the backlight it depends on is there."""
    product = product_with_added_declaration(
        demo_product(),
        DeclaredValue(attribute_id=HEATING, chosen=ChosenValue(value_id=NO_HEATING, quantity=None)),
    )

    configuration = inquiry_configuration(
        product=product,
        attributes=demo_attributes(),
        dimensions=_DIMENSIONS,
        selections={BACKLIGHT: ChosenValue(value_id=CONTOUR, quantity=None)},
    )

    assert configuration.values == (
        _BLADE,
        _SHAPE,
        _FRAME,
        _CONTOUR,
        _MOUNT,
        ConfigurationValue(attribute_name="Подогрев", value_name="Без подогрева", quantity=None),
    )


def test_a_declared_dependent_attribute_stays_out_while_its_parent_is_absent() -> None:
    """Heating under "no backlight" is not a feature of the mirror, declared or not."""
    product = product_with_added_declaration(
        demo_product(),
        DeclaredValue(attribute_id=HEATING, chosen=ChosenValue(value_id=NO_HEATING, quantity=None)),
    )

    configuration = inquiry_configuration(
        product=product,
        attributes=demo_attributes(),
        dimensions=_DIMENSIONS,
        selections={},
    )

    assert configuration.values == (_BLADE, _SHAPE, _FRAME, _NO_BACKLIGHT, _MOUNT)


def test_a_numeric_attribute_enters_the_configuration_as_the_quantity_the_customer_typed() -> None:
    """A count has no dictionary row to name: the specification carries the number itself."""
    configuration = inquiry_configuration(
        product=demo_numeric_product(quantity=Decimal(1)),
        attributes=[demo_cutouts()],
        dimensions=_DIMENSIONS,
        selections={CUTOUTS: ChosenValue(value_id=None, quantity=Decimal("2.5"))},
    )

    assert configuration.values == (
        ConfigurationValue(attribute_name="Вырезы", value_name=None, quantity=Decimal("2.5")),
    )


def test_a_declared_count_enters_the_configuration_when_the_customer_typed_none() -> None:
    """The product's own count is what gets made, and the manager reads it off the snapshot."""
    configuration = inquiry_configuration(
        product=demo_numeric_product(quantity=Decimal(1)),
        attributes=[demo_cutouts()],
        dimensions=_DIMENSIONS,
        selections={},
    )

    assert configuration.values == (ConfigurationValue(attribute_name="Вырезы", value_name=None, quantity=Decimal(1)),)
