from collections.abc import Sequence
from uuid import UUID

import structlog
from pydantic import BaseModel, Field, model_validator

from memiro.application.common.customer_selection import Selection, customer_selections
from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import (
    MAX_COMMENT_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_INQUIRY_ITEMS,
    MAX_NAME_LENGTH,
    MAX_PHONE_LENGTH,
    MAX_SELECTIONS,
    MAX_SIDE_MM,
    MAX_WISH_LENGTH,
    MIN_NAME_LENGTH,
    MIN_PHONE_LENGTH,
    MIN_SIDE_MM,
)
from memiro.application.common.notification import InquiryNotificationBus
from memiro.application.errors.catalog import ProductNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.common.identifiers import AttributeId, ProductId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.inquiry.entity import (
    ConfigurationValue,
    InquiryConfiguration,
    InquiryData,
    InquiryItemData,
    InquirySource,
    ensure_new_inquiry_is_accepted,
    inquiry_factory,
)
from memiro.entities.pricing.pricing_service import price_product_for_customer
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import PricingVerdict
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

CURRENT_CONSENT_VERSION = "2026-08-31"

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


class SubmitInquiryForm(BaseModel):
    """The visitor data for one inquiry and its optional product selection."""

    source: InquirySource
    name: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    phone: str = Field(min_length=MIN_PHONE_LENGTH, max_length=MAX_PHONE_LENGTH)
    email: str | None = Field(default=None, max_length=MAX_EMAIL_LENGTH)
    consent: bool
    comment: str = Field(max_length=MAX_COMMENT_LENGTH)
    items: list[InquiryItemForm] = Field(default_factory=list[InquiryItemForm], max_length=MAX_INQUIRY_ITEMS)


class CreatedInquiry(BaseModel):
    """The public acknowledgement of a stored inquiry."""

    id: UUID


@interactor
class SubmitInquiry:
    """Store a visitor's inquiry together with server-built item snapshots."""

    uow: UoW
    product_gateway: ProductGateway
    pricing_settings_gateway: PricingSettingsGateway
    attribute_gateway: AttributeGateway
    event_bus: InquiryNotificationBus
    clock: Clock

    async def execute(self, data: SubmitInquiryForm) -> CreatedInquiry:
        """Reprice all submitted configurations and commit one inquiry aggregate."""
        logger.debug("Submitting inquiry", source=data.source, item_count=len(data.items))
        ensure_new_inquiry_is_accepted(data.source, len(data.items), data.comment, consent=data.consent)
        items = await self._items(data.items)
        inquiry = inquiry_factory(
            InquiryData(
                source=data.source,
                name=data.name,
                phone=data.phone,
                email=data.email,
                comment=data.comment,
                consent=data.consent,
                consent_version=CURRENT_CONSENT_VERSION,
                items=tuple(items),
            ),
            self.clock,
        )
        self.uow.add(inquiry)
        await self.uow.commit()
        await self.event_bus.notify(inquiry.id)
        logger.info("Inquiry submitted", inquiry_id=inquiry.id, item_count=len(inquiry.items))
        return CreatedInquiry(id=inquiry.id)

    async def _items(self, forms: Sequence[InquiryItemForm]) -> list[InquiryItemData]:
        """Build server-owned snapshots for every item before the aggregate is created."""
        if not forms:
            return []
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("Inquiry submitted before pricing settings were created")
            raise PricingSettingsNotFoundError
        attributes = await self.attribute_gateway.list_with_values()
        return [await self._item(form, attributes, settings) for form in forms]

    async def _item(
        self,
        form: InquiryItemForm,
        attributes: Sequence[Attribute],
        settings: PricingSettings,
    ) -> InquiryItemData:
        """Load, price and freeze one product configuration."""
        product_id: ProductId = form.product_id
        product = await self.product_gateway.get(product_id)
        if product is None:
            logger.warning("Inquiry named an unknown product", product_id=product_id)
            raise ProductNotFoundError
        dimensions = Dimensions(width=Millimeters(form.width_mm), height=Millimeters(form.height_mm))
        selections = customer_selections(product, attributes, form.selections)
        quotation = price_product_for_customer(
            product=product,
            attributes=attributes,
            settings=settings,
            dimensions=dimensions,
            selections=selections,
        )
        return InquiryItemData(
            product_id=product.id,
            product_name=product.name,
            price_from=product.price_from,
            configuration=(
                None
                if quotation.verdict is PricingVerdict.NOT_PRICEABLE
                else _configuration(dimensions, form.selections, attributes)
            ),
            calculated_price=quotation.total,
            verdict=quotation.verdict,
            wish=form.wish,
        )


def _configuration(
    dimensions: Dimensions,
    selections: Sequence[Selection],
    attributes: Sequence[Attribute],
) -> InquiryConfiguration:
    """Replace dictionary identifiers in a customer selection with names for the snapshot."""
    index = {attribute.id: attribute for attribute in attributes}
    values: list[ConfigurationValue] = []
    for selection in selections:
        attribute_id: AttributeId = selection.attribute_id
        attribute = index[attribute_id]
        value = attribute.value(selection.value_id) if selection.value_id is not None else None
        values.append(
            ConfigurationValue(
                attribute_name=attribute.name,
                value_name=value.name if value is not None else None,
                quantity=selection.quantity,
            )
        )
    return InquiryConfiguration(dimensions=dimensions, values=tuple(values))
