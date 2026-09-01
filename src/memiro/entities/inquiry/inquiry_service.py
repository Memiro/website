from memiro.entities.catalog.product.entity import Product
from memiro.entities.inquiry.entity import InquiryConfiguration, InquiryItemData
from memiro.entities.pricing.quotation import PricingVerdict, Quotation


def inquiry_item_snapshot(
    *,
    product: Product,
    configuration: InquiryConfiguration,
    quotation: Quotation,
    wish: str,
) -> InquiryItemData:
    """Freeze one repriced configuration into the position snapshot the manager reads.

    A cross-aggregate rule: the product, the calculation and the customer's
    configuration meet here and nowhere else (§6.3(c)).
    """
    return InquiryItemData(
        product_id=product.id,
        product_name=product.name,
        price_from=product.price_from,
        configuration=None if quotation.verdict is PricingVerdict.NOT_PRICEABLE else configuration,
        calculated_price=quotation.total,
        verdict=quotation.verdict,
        wish=wish,
    )
