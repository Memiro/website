"""The demo dictionary the xlsx workbook was checked against.

The tariffs are the owner's demo numbers (`.scratch/new-site/demo/seed_pricing.py`),
and the tests speak in them by name so an expected price can be checked by
hand against the workbook.
"""

from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind, AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId, ProductId
from memiro.entities.common.measure import Area, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_settings import PRICING_SETTINGS_ID, PricingSettings, SizeSurcharge


def _id(name: str) -> UUID:
    """Derive a stable identifier from a name: readable in failures, equal across runs."""
    return uuid5(NAMESPACE_URL, f"memiro/test/{name}")


BLADE: AttributeId = _id("blade")
SILVER: AttributeValueId = _id("silver")
GRAPHITE: AttributeValueId = _id("graphite")

FRAME: AttributeId = _id("frame")
ALUMINIUM: AttributeValueId = _id("aluminium")
NO_FRAME: AttributeValueId = _id("no-frame")

MOUNT: AttributeId = _id("mount")
WITH_MOUNT: AttributeValueId = _id("with-mount")
NO_MOUNT: AttributeValueId = _id("no-mount")

SHAPE: AttributeId = _id("shape")
RECTANGULAR: AttributeValueId = _id("rectangular")
ROUND: AttributeValueId = _id("round")

BACKLIGHT: AttributeId = _id("backlight")
CONTOUR: AttributeValueId = _id("contour")
NO_BACKLIGHT: AttributeValueId = _id("no-backlight")

# Heating is in the dictionary but not on the canonical mirror: the customer
# replaces what the product declares, he does not add a setting it never had.
HEATING: AttributeId = _id("heating")
WITH_HEATING: AttributeValueId = _id("with-heating")
NO_HEATING: AttributeValueId = _id("no-heating")

CUTOUTS: AttributeId = _id("cut-outs")
CUTOUT: AttributeValueId = _id("cut-out")

CATEGORY: CategoryId = _id("mirrors")
PRODUCT: ProductId = _id("mirror-in-a-frame")

FREE = Rate(amount=Money(amount=Decimal(0)), unit=Unit.PIECE)


def _rate(amount: str, unit: Unit) -> Rate:
    return Rate(amount=Money(amount=Decimal(amount)), unit=unit)


def demo_blade() -> Attribute:
    """Build the blade attribute: silver at 4 500 and graphite at 7 000 per square metre."""
    return Attribute(
        id=BLADE,
        category_id=CATEGORY,
        name="Тип полотна",
        sort_order=1,
        values=[
            AttributeValue(
                id=SILVER,
                name="Серебро",
                rate=_rate("4500", Unit.SQUARE_METER),
                scaled_by_shape=True,
                sort_order=1,
                scaled_by_size_surcharge=True,
            ),
            AttributeValue(
                id=GRAPHITE,
                name="Графит",
                rate=_rate("7000", Unit.SQUARE_METER),
                scaled_by_shape=True,
                sort_order=2,
                scaled_by_size_surcharge=True,
            ),
        ],
    )


def demo_shape() -> Attribute:
    """Build the shape attribute: a rectangle costs what it costs, a circle one and a half of it."""
    return Attribute(
        id=SHAPE,
        category_id=CATEGORY,
        name="Форма",
        sort_order=2,
        values=[
            AttributeValue(
                id=RECTANGULAR,
                name="Прямоугольное",
                rate=_rate("1.0", Unit.FACTOR),
                scaled_by_shape=False,
                sort_order=1,
            ),
            AttributeValue(
                id=ROUND,
                name="Круглое",
                rate=_rate("1.5", Unit.FACTOR),
                scaled_by_shape=False,
                sort_order=2,
            ),
        ],
    )


def demo_frame() -> Attribute:
    """Build the frame attribute: aluminium at 2 200 per linear metre, or no frame at all."""
    return Attribute(
        id=FRAME,
        category_id=CATEGORY,
        name="Рама",
        sort_order=3,
        values=[
            AttributeValue(
                id=ALUMINIUM,
                name="Алюминий",
                rate=_rate("2200", Unit.LINEAR_METER),
                scaled_by_shape=True,
                sort_order=1,
            ),
            AttributeValue(
                id=NO_FRAME,
                name="Без рамы",
                rate=FREE,
                scaled_by_shape=False,
                sort_order=2,
                marks_absence=True,
            ),
        ],
    )


def demo_backlight() -> Attribute:
    """Build the backlight attribute: a contour tape at 2 500 per linear metre, or none."""
    return Attribute(
        id=BACKLIGHT,
        category_id=CATEGORY,
        name="Подсветка",
        sort_order=4,
        values=[
            # The tape is measured in the same linear metre as the frame
            # but does not grow on a curved cut — hence its own flag.
            AttributeValue(
                id=CONTOUR,
                name="Контурная",
                rate=_rate("2500", Unit.LINEAR_METER),
                scaled_by_shape=False,
                sort_order=1,
            ),
            AttributeValue(
                id=NO_BACKLIGHT,
                name="Без подсветки",
                rate=FREE,
                scaled_by_shape=False,
                sort_order=2,
                marks_absence=True,
            ),
        ],
    )


def demo_mount() -> Attribute:
    """Build the mount attribute: 500 for the piece, or nothing for none."""
    return Attribute(
        id=MOUNT,
        category_id=CATEGORY,
        name="Крепление",
        sort_order=5,
        values=[
            AttributeValue(
                id=WITH_MOUNT,
                name="С креплением",
                rate=_rate("500", Unit.PIECE),
                scaled_by_shape=False,
                sort_order=1,
            ),
            AttributeValue(
                id=NO_MOUNT,
                name="Без крепления",
                rate=FREE,
                scaled_by_shape=False,
                sort_order=2,
                marks_absence=True,
            ),
        ],
    )


def demo_heating() -> Attribute:
    """Build the heating attribute — the one the canonical mirror does not declare."""
    return Attribute(
        id=HEATING,
        category_id=CATEGORY,
        name="Подогрев",
        kind=AttributeKind.SELECT,
        parent_ids=(BACKLIGHT,),
        is_customer_changeable=True,
        sort_order=6,
        values=[
            AttributeValue(
                id=WITH_HEATING,
                name="С подогревом",
                rate=_rate("3500", Unit.PIECE),
                scaled_by_shape=False,
                sort_order=1,
            ),
            AttributeValue(
                id=NO_HEATING,
                name="Без подогрева",
                rate=FREE,
                scaled_by_shape=False,
                sort_order=2,
                marks_absence=True,
            ),
        ],
    )


def demo_cutouts() -> Attribute:
    """Build the numeric cut-out attribute: one hundred roubles for each cut-out."""
    return Attribute(
        id=CUTOUTS,
        category_id=CATEGORY,
        name="Вырезы",
        kind=AttributeKind.NUMBER,
        parent_ids=(),
        is_customer_changeable=True,
        sort_order=7,
        values=[
            AttributeValue(
                id=CUTOUT,
                name="Вырез",
                rate=_rate("100", Unit.PIECE),
                scaled_by_shape=False,
                sort_order=1,
            )
        ],
    )


def demo_attributes() -> list[Attribute]:
    """Build the slice of the owner's dictionary the price of a mirror is made of."""
    return [
        demo_blade(),
        demo_shape(),
        demo_frame(),
        demo_backlight(),
        demo_mount(),
        demo_heating(),
    ]


def demo_product(*, blade: AttributeValueId = SILVER) -> Product:
    """Build the canonical mirror: silver blade, aluminium frame, a mount, no backlight."""
    return Product(
        id=PRODUCT,
        category_id=CATEGORY,
        name="Зеркало в раме",
        slug="zerkalo-v-rame",
        is_published=True,
        hides_calculated_price=False,
        declared_values=[
            DeclaredValue(attribute_id=BLADE, configured=ConfiguredValue(value_id=blade, quantity=None)),
            DeclaredValue(
                attribute_id=SHAPE,
                configured=ConfiguredValue(value_id=RECTANGULAR, quantity=None),
            ),
            DeclaredValue(
                attribute_id=FRAME,
                configured=ConfiguredValue(value_id=ALUMINIUM, quantity=None),
            ),
            DeclaredValue(
                attribute_id=BACKLIGHT,
                configured=ConfiguredValue(value_id=NO_BACKLIGHT, quantity=None),
            ),
            DeclaredValue(
                attribute_id=MOUNT,
                configured=ConfiguredValue(value_id=WITH_MOUNT, quantity=None),
            ),
        ],
    )


def demo_product_without(attribute_id: AttributeId) -> Product:
    """Build the canonical mirror without one declaration."""
    product = demo_product()
    return replace(
        product,
        declared_values=[
            declaration for declaration in product.declared_values if declaration.attribute_id != attribute_id
        ],
    )


def demo_product_with_value(attribute_id: AttributeId, value_id: AttributeValueId | None) -> Product:
    """Build the canonical mirror with one declaration replaced."""
    product = demo_product()
    return replace(
        product,
        declared_values=[
            replace(
                declaration,
                configured=ConfiguredValue(value_id=value_id, quantity=None),
            )
            if declaration.attribute_id == attribute_id
            else declaration
            for declaration in product.declared_values
        ],
    )


def product_with_added_declaration(product: Product, declaration: DeclaredValue) -> Product:
    """Build a product copy with one dependent declaration appended."""
    return replace(product, declared_values=[*product.declared_values, declaration])


def demo_attributes_replacing(replacement: Attribute) -> list[Attribute]:
    """Build the demo dictionary with one aggregate replaced by identifier."""
    return [replacement if attribute.id == replacement.id else attribute for attribute in demo_attributes()]


def demo_attributes_with_changeability(
    attribute_id: AttributeId,
    *,
    is_customer_changeable: bool,
) -> list[Attribute]:
    """Build the demo dictionary with one customer-changeability flag replaced."""
    return [
        replace(attribute, is_customer_changeable=is_customer_changeable) if attribute.id == attribute_id else attribute
        for attribute in demo_attributes()
    ]


def demo_numeric_product(*, quantity: Decimal) -> Product:
    """Build a product whose only priced declaration is a fractional count of cut-outs."""
    return Product(
        id=PRODUCT,
        category_id=CATEGORY,
        name="Зеркало с вырезами",
        slug="zerkalo-s-vyrezami",
        is_published=True,
        hides_calculated_price=False,
        declared_values=[
            DeclaredValue(
                attribute_id=CUTOUTS,
                configured=ConfiguredValue(value_id=None, quantity=quantity),
            ),
        ],
    )


def demo_defaults() -> dict[AttributeId, AttributeValueId]:
    """Tell what the canonical mirror declares — the configuration a customer starts from."""
    return {
        declaration.attribute_id: cast("AttributeValueId", declaration.configured.value_id)
        for declaration in demo_product().declared_values
    }


def demo_choices() -> dict[AttributeId, list[AttributeValueId]]:
    """Tell what a customer may put in place of each default: the rows of the attributes the mirror declares."""
    values = {attribute.id: [value.id for value in attribute.values] for attribute in demo_attributes()}
    return {attribute_id: values[attribute_id] for attribute_id in demo_defaults()}


def demo_size_surcharge(
    *,
    from_long_side_mm: int = 2200,
    factor: str = "1.25",
) -> SizeSurcharge:
    """Build the owner's first size-surcharge tier."""
    return SizeSurcharge(
        from_long_side_mm=Millimeters(value=from_long_side_mm),
        factor=Decimal(factor),
    )


def demo_settings(*, size_surcharges: Sequence[SizeSurcharge] = ()) -> PricingSettings:
    """Build the owner's demo bounds: 0.25 m² of area and 2 000 ₽ of order."""
    return PricingSettings(
        # The known id of the single row: the gateway fetches it by this and
        # nothing else, so the fixture must speak the production constant.
        id=PRICING_SETTINGS_ID,
        min_area=Area(value=Decimal("0.25")),
        min_order_total=Money(amount=Decimal(2000)),
        _size_surcharges=list(size_surcharges),
    )
