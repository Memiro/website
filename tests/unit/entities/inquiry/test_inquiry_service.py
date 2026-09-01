from decimal import Decimal

from memiro.entities.common.identifiers import ProductId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.inquiry.entity import InquiryConfiguration, InquiryItemData
from memiro.entities.inquiry.inquiry_service import inquiry_item_snapshot
from memiro.entities.pricing.quotation import PricingVerdict, Quotation
from tests.common.factory.catalog import demo_product

_MIRROR = demo_product()
_PRODUCT: ProductId = _MIRROR.id
_PRICE = Money(amount=Decimal(8900))
_CONFIGURATION = InquiryConfiguration(
    dimensions=Dimensions(width=Millimeters(value=800), height=Millimeters(value=600)),
    values=(),
)


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
