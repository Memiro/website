from collections.abc import Mapping, Sequence

from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import AttributeId
from memiro.entities.common.measure import Dimensions
from memiro.entities.inquiry.entity import ConfigurationValue, InquiryConfiguration, InquiryItemData
from memiro.entities.pricing.pricing_service import applicable_values
from memiro.entities.pricing.quotation import PricingVerdict, Quotation


def inquiry_configuration(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    dimensions: Dimensions,
    selections: Mapping[AttributeId, ChosenValue],
) -> InquiryConfiguration:
    """Name the whole specification of the mirror: every applicable value, the customer's choice over the product's own.

    The snapshot outlives the product's markup, so it carries the values the
    customer never touched too; which of them he chose it does not say
    (``Inquiry``, rule 21).
    """
    index = {attribute.id: attribute for attribute in attributes}
    values = tuple(
        ConfigurationValue(
            attribute_name=index[attribute_id].name,
            value_name=None if quantity is not None else value.name,
            quantity=quantity,
        )
        for attribute_id, value, quantity in applicable_values(product, attributes, selections)
    )
    return InquiryConfiguration(dimensions=dimensions, values=values)


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
