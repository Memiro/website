"""The one owner path into the pricing service, shared by saving a variant and repricing one.

Both ask the same question and must get the same number; they differ only in
what an uncalculable configuration means — the owner's own refusal while he is
saving, a variant to leave alone while the catalogue is being repriced. A price
the owner typed answers before the question is asked at all (ADR-0017).
"""

from collections.abc import Sequence

import structlog

from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product, Variant, VariantData
from memiro.entities.common.money import Money
from memiro.entities.errors.product import InvalidVariantConfigurationError
from memiro.entities.pricing.pricing_service import is_product_priceable, price_product
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro_common.clock import Clock
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


def variant_price(
    data: VariantData,
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
) -> Money | None:
    """Price one variant configuration, or say that it carries no applicable paid value."""
    selections = {override.attribute_id: override.chosen for override in data.overrides}
    if not is_product_priceable(product, attributes, selections):
        return None
    quotation = price_product(
        product=product,
        attributes=attributes,
        settings=settings,
        dimensions=data.dimensions,
        selections=selections,
    )
    return quotation.settled_total()


def settled_variant_price(
    data: VariantData,
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
) -> Money:
    """Take the price the owner typed, or price the variant he is saving; neither is his own refusal."""
    if data.manual_price is not None:
        return data.manual_price
    price = variant_price(data, product=product, attributes=attributes, settings=settings)
    if price is None:
        raise InvalidVariantConfigurationError(
            message="A variant configuration must contain every applicable paid value or a price of its own",
        )
    return price


def repriced_variants(
    product: Product,
    *,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    clock: Clock,
) -> bool:
    """Reprice every calculated variant of one product, and say whether any of them took a new price."""
    moved = False
    for variant in product.variants:
        if variant.price_is_manual:
            continue
        configuration = _same_configuration(variant)
        price = variant_price(configuration, product=product, attributes=attributes, settings=settings)
        if price is None:
            logger.warning(
                "A variant is no longer priceable and keeps the price it had",
                product_id=product.id,
                variant_id=variant.id,
            )
            continue
        product.change_variant(variant, configuration, price=price, clock=clock)
        moved = True
    return moved


def _same_configuration(variant: Variant) -> VariantData:
    """Restate one variant as the command data of the aggregate, changing nothing but its price."""
    # Only variants the calculation prices reach here, so the restated data
    # carries no price of the owner's own (ADR-0017).
    return VariantData(
        dimensions=variant.dimensions,
        overrides=variant.overrides,
        sort_order=variant.sort_order,
    )
