from collections.abc import Sequence
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import (
    MAX_COMMENT_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_INQUIRY_ITEMS,
    MAX_NAME_LENGTH,
    MAX_PHONE_LENGTH,
    MIN_NAME_LENGTH,
    MIN_PHONE_LENGTH,
)
from memiro.application.common.notification import InquiryNotificationBus
from memiro.application.errors.catalog import ProductNotFoundError
from memiro.application.submit_inquiry.config import LegalConfig
from memiro.application.submit_inquiry.shared import (
    InquiryItemForm,
    PreviewedItem,
    PricingContext,
    item_snapshot,
    pricing_context,
    projected_item,
)
from memiro.entities.common.identifiers import ProductId
from memiro.entities.inquiry.consent import given_consent
from memiro.entities.inquiry.entity import (
    InquiryData,
    InquiryItemData,
    InquirySource,
    ensure_new_inquiry_shape,
    inquiry_factory,
)
from memiro.entities.inquiry.phone import normalized_phone
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class SubmitInquiryForm(BaseModel):
    """The visitor data for one inquiry and its optional product selection."""

    source: InquirySource
    name: str = Field(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    phone: str = Field(min_length=MIN_PHONE_LENGTH, max_length=MAX_PHONE_LENGTH)
    email: str | None = Field(default=None, max_length=MAX_EMAIL_LENGTH)
    consent: bool
    comment: str = Field(max_length=MAX_COMMENT_LENGTH)
    items: list[InquiryItemForm] = Field(default_factory=list[InquiryItemForm], max_length=MAX_INQUIRY_ITEMS)


class SubmittedInquiry(BaseModel):
    """The stored inquiry as the customer reads it back: its identifier and the stored positions, projected."""

    id: UUID
    items: list[PreviewedItem]


@interactor
class SubmitInquiry:
    """Store a visitor's inquiry together with server-built item snapshots."""

    uow: UoW
    pricing_settings_gateway: PricingSettingsGateway
    attribute_gateway: AttributeGateway
    product_gateway: ProductGateway
    event_bus: InquiryNotificationBus
    clock: Clock
    legal: LegalConfig

    async def execute(self, data: SubmitInquiryForm) -> SubmittedInquiry:
        """Reprice all submitted configurations and commit one inquiry aggregate."""
        logger.debug("Submitting inquiry", source=data.source, item_count=len(data.items))
        consent = given_consent(given=data.consent, version=self.legal.consent_version)
        ensure_new_inquiry_shape(data.source, len(data.items), data.comment)
        phone = normalized_phone(data.phone)
        items = await self._items(data.items)
        inquiry = inquiry_factory(
            InquiryData(
                source=data.source,
                name=data.name,
                phone=phone,
                email=data.email,
                comment=data.comment,
                consent=consent,
                items=tuple(items),
            ),
            self.clock,
        )
        self.uow.add(inquiry)
        await self.uow.commit()
        await self.event_bus.notify(inquiry.id)
        logger.info("Inquiry submitted", inquiry_id=inquiry.id, item_count=len(inquiry.items))
        return SubmittedInquiry(id=inquiry.id, items=[projected_item(item) for item in items])

    async def _items(self, forms: Sequence[InquiryItemForm]) -> list[InquiryItemData]:
        """Build server-owned snapshots for every item before the aggregate is created."""
        if not forms:
            return []
        context = await pricing_context(self.pricing_settings_gateway, self.attribute_gateway)
        return [await self._item(form, context) for form in forms]

    async def _item(self, form: InquiryItemForm, context: PricingContext) -> InquiryItemData:
        """Load, price and freeze one product configuration."""
        product_id: ProductId = form.product_id
        product = await self.product_gateway.get(product_id)
        if product is None:
            logger.warning("Inquiry named an unknown product", product_id=product_id)
            raise ProductNotFoundError
        return item_snapshot(form, product, context)
