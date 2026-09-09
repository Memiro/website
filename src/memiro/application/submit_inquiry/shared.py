from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field, model_validator

from memiro.application.common.customer_selection import Selection, customer_selections
from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.input_limits import MAX_SELECTIONS, MAX_SIDE_MM, MAX_WISH_LENGTH, MIN_SIDE_MM
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.inquiry.entity import InquiryConfiguration, InquiryItemData
from memiro.entities.inquiry.inquiry_service import inquiry_configuration, inquiry_item_snapshot
from memiro.entities.pricing.pricing_service import price_product_for_customer
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import PricingVerdict, customer_price
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class InquiryItemForm(BaseModel):
    """One chosen product submitted in a visitor selection."""

    product_id: UUID
    width_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    height_mm: int = Field(ge=MIN_SIDE_MM, le=MAX_SIDE_MM)
    selections: list[Selection] = Field(default_factory=list[Selection], max_length=MAX_SELECTIONS)
    wish: str = Field(max_length=MAX_WISH_LENGTH)

    @model_validator(mode="after")
    def _one_choice_per_attribute(self) -> "InquiryItemForm":
        """Refuse a second choice whose saved snapshot would be ambiguous."""
        attribute_ids = [selection.attribute_id for selection in self.selections]
        if len(set(attribute_ids)) != len(attribute_ids):
            msg = "An attribute can be chosen only once"
            raise ValueError(msg)
        return self


class PreviewedValue(BaseModel):
    """One value of the specification, by name."""

    attribute_name: str
    value_name: str | None
    quantity: Decimal | None


class PreviewedConfiguration(BaseModel):
    """The size and the specification of one position, as the snapshot names them."""

    width_mm: int
    height_mm: int
    values: list[PreviewedValue]


class PreviewedItem(BaseModel):
    """One position as the customer may see it: the snapshot minus the breakdown and the hidden price."""

    # Empty except for ``product_id`` and ``wish`` when the product is not
    # available: the storefront then offers to remove the position.

    product_id: UUID
    is_available: bool
    product_name: str | None
    price_from: Decimal | None
    verdict: PricingVerdict | None
    price: Decimal | None
    configuration: PreviewedConfiguration | None
    wish: str


@dataclass(frozen=True, slots=True)
class PricingContext:
    """What every position of one request is priced against, loaded once."""

    settings: PricingSettings
    attributes: Sequence[Attribute]


async def pricing_context(
    pricing_settings_gateway: PricingSettingsGateway,
    attribute_gateway: AttributeGateway,
) -> PricingContext:
    """Load the settings and the dictionary once for every position of a request."""
    settings = await pricing_settings_gateway.get_with_surcharges()
    if settings is None:
        logger.warning("Inquiry positions asked for before pricing settings were created")
        raise PricingSettingsNotFoundError
    return PricingContext(settings=settings, attributes=await attribute_gateway.list_with_values())


def item_snapshot(form: InquiryItemForm, product: Product, context: PricingContext) -> InquiryItemData:
    """Price and freeze one product configuration the way it is stored — preview and submission alike."""
    dimensions = Dimensions(width=Millimeters(form.width_mm), height=Millimeters(form.height_mm))
    selections = customer_selections(product, context.attributes, form.selections)
    quotation = price_product_for_customer(
        product=product,
        attributes=context.attributes,
        settings=context.settings,
        dimensions=dimensions,
        selections=selections,
    )
    return inquiry_item_snapshot(
        product=product,
        configuration=inquiry_configuration(
            product=product,
            attributes=context.attributes,
            dimensions=dimensions,
            selections=selections,
        ),
        quotation=quotation,
        wish=form.wish,
    )


def _projected_configuration(configuration: InquiryConfiguration | None) -> PreviewedConfiguration | None:
    """Project the size and the named values of one snapshot."""
    if configuration is None:
        return None
    return PreviewedConfiguration(
        width_mm=configuration.dimensions.width.value,
        height_mm=configuration.dimensions.height.value,
        values=[
            PreviewedValue(attribute_name=value.attribute_name, value_name=value.value_name, quantity=value.quantity)
            for value in configuration.values
        ],
    )


def projected_item(snapshot: InquiryItemData) -> PreviewedItem:
    """Project one snapshot for the customer: the price through the storefront gate, the breakdown withheld."""
    price = customer_price(snapshot.verdict, snapshot.calculated_price)
    return PreviewedItem(
        product_id=snapshot.product_id,
        is_available=True,
        product_name=snapshot.product_name,
        price_from=snapshot.price_from.amount if snapshot.price_from is not None else None,
        verdict=snapshot.verdict,
        price=price.amount if price is not None else None,
        configuration=_projected_configuration(snapshot.configuration),
        wish=snapshot.wish,
    )


def unavailable_item(form: InquiryItemForm) -> PreviewedItem:
    """Answer a position whose product is gone or off the storefront with nothing but what was sent."""
    return PreviewedItem(
        product_id=form.product_id,
        is_available=False,
        product_name=None,
        price_from=None,
        verdict=None,
        price=None,
        configuration=None,
        wish=form.wish,
    )
