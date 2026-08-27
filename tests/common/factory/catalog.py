"""The demo dictionary the xlsx workbook was checked against.

The tariffs are the owner's demo numbers (`.scratch/new-site/demo/seed_pricing.py`),
and the tests speak in them by name so an expected price can be checked by
hand against the workbook.
"""

from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from memiro.entities.catalog.attribute.entity import Attribute, AttributeValue
from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.catalog.product.entity import DeclaredValue, Product
from memiro.entities.common.identifiers import (
    AttributeId,
    AttributeValueId,
    PricingSettingsId,
    ProductId,
)
from memiro.entities.common.measure import Area
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_settings import PricingSettings


def _id(name: str) -> UUID:
    """Derive a stable identifier from a name: readable in failures, equal across runs."""
    return uuid5(NAMESPACE_URL, f"memiro/test/{name}")


BLADE = AttributeId(_id("blade"))
SILVER = AttributeValueId(_id("silver"))
GRAPHITE = AttributeValueId(_id("graphite"))

FRAME = AttributeId(_id("frame"))
ALUMINIUM = AttributeValueId(_id("aluminium"))
NO_FRAME = AttributeValueId(_id("no-frame"))

MOUNT = AttributeId(_id("mount"))
WITH_MOUNT = AttributeValueId(_id("with-mount"))
NO_MOUNT = AttributeValueId(_id("no-mount"))

SHAPE = AttributeId(_id("shape"))
RECTANGULAR = AttributeValueId(_id("rectangular"))
ROUND = AttributeValueId(_id("round"))

BACKLIGHT = AttributeId(_id("backlight"))
CONTOUR = AttributeValueId(_id("contour"))
NO_BACKLIGHT = AttributeValueId(_id("no-backlight"))

PRODUCT = ProductId(_id("mirror-in-a-frame"))
PRICING_SETTINGS = PricingSettingsId(_id("pricing-settings"))

FREE = Rate(amount=Money(amount=Decimal(0)), unit=Unit.PIECE)


def _rate(amount: str, unit: Unit) -> Rate:
    return Rate(amount=Money(amount=Decimal(amount)), unit=unit)


def demo_attributes() -> list[Attribute]:
    """Build the slice of the owner's dictionary the price of a mirror is made of."""
    return [
        Attribute(
            id=BLADE,
            name="Тип полотна",
            sort_order=1,
            values=[
                AttributeValue(
                    id=SILVER,
                    name="Серебро",
                    rate=_rate("4500", Unit.SQUARE_METER),
                    scaled_by_shape=True,
                    sort_order=1,
                ),
                AttributeValue(
                    id=GRAPHITE,
                    name="Графит",
                    rate=_rate("7000", Unit.SQUARE_METER),
                    scaled_by_shape=True,
                    sort_order=2,
                ),
            ],
        ),
        Attribute(
            id=SHAPE,
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
        ),
        Attribute(
            id=FRAME,
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
                AttributeValue(id=NO_FRAME, name="Без рамы", rate=FREE, scaled_by_shape=False, sort_order=2),
            ],
        ),
        Attribute(
            id=BACKLIGHT,
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
                AttributeValue(id=NO_BACKLIGHT, name="Без подсветки", rate=FREE, scaled_by_shape=False, sort_order=2),
            ],
        ),
        Attribute(
            id=MOUNT,
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
                AttributeValue(id=NO_MOUNT, name="Без крепления", rate=FREE, scaled_by_shape=False, sort_order=2),
            ],
        ),
    ]


def demo_product(*, blade: AttributeValueId = SILVER) -> Product:
    """Build the canonical mirror: silver blade, aluminium frame, a mount, no backlight."""
    return Product(
        id=PRODUCT,
        name="Зеркало в раме",
        slug="zerkalo-v-rame",
        declared_values=[
            DeclaredValue(attribute_id=BLADE, value_id=blade),
            DeclaredValue(attribute_id=SHAPE, value_id=RECTANGULAR),
            DeclaredValue(attribute_id=FRAME, value_id=ALUMINIUM),
            DeclaredValue(attribute_id=BACKLIGHT, value_id=NO_BACKLIGHT),
            DeclaredValue(attribute_id=MOUNT, value_id=WITH_MOUNT),
        ],
    )


def demo_settings() -> PricingSettings:
    """Build the owner's demo bounds: 0.25 m² of area and 2 000 ₽ of order."""
    return PricingSettings(
        id=PRICING_SETTINGS,
        min_area=Area(value=Decimal("0.25")),
        min_order_total=Money(amount=Decimal(2000)),
    )
