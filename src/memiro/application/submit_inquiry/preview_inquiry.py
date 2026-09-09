import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import MAX_INQUIRY_ITEMS
from memiro.application.submit_inquiry.shared import (
    InquiryItemForm,
    PreviewedItem,
    PricingContext,
    item_snapshot,
    pricing_context,
    projected_item,
    unavailable_item,
)
from memiro.entities.common.identifiers import ProductId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class PreviewInquiryForm(BaseModel):
    """The positions of a selection the customer is about to send, without contacts or consent."""

    items: list[InquiryItemForm] = Field(min_length=1, max_length=MAX_INQUIRY_ITEMS)


class InquiryPreview(BaseModel):
    """What the selection would be stored as, position by position, in the order it came."""

    items: list[PreviewedItem]


@interactor
class PreviewInquiry:
    """Show a selection the way a submission would store it, storing nothing."""

    pricing_settings_gateway: PricingSettingsGateway
    attribute_gateway: AttributeGateway
    product_gateway: ProductGateway

    async def execute(self, data: PreviewInquiryForm) -> InquiryPreview:
        """Build every position with the code of a submission and project it for the customer."""
        logger.debug("Previewing inquiry", item_count=len(data.items))
        context = await pricing_context(self.pricing_settings_gateway, self.attribute_gateway)
        return InquiryPreview(items=[await self._item(form, context) for form in data.items])

    async def _item(self, form: InquiryItemForm, context: PricingContext) -> PreviewedItem:
        """Answer one position, an unavailable product as an empty position rather than a refusal."""
        product_id: ProductId = form.product_id
        product = await self.product_gateway.get(product_id)
        if product is None or not product.is_published:
            return unavailable_item(form)
        return projected_item(item_snapshot(form, product, context))
