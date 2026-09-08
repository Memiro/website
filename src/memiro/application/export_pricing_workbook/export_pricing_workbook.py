from uuid import UUID

import structlog
from pydantic import BaseModel, model_validator

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.category import CategoryGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.gateway.workbook import (
    CheckedSize,
    PricingWorkbookRenderer,
    PricingWorkbookSource,
)
from memiro.application.errors.catalog import CategoryNotFoundError, ProductNotFoundError
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import CategoryId, ProductId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.pricing.pricing_service import is_product_priceable, price_product
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import Quotation
from memiro_common.interactor import interactor
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)

# The sizes of the check sheet: one small enough to rest on the minimum
# billable area, two ordinary ones and one large enough to reach the size
# surcharge. Together they show every bottom rule of the calculation at once.
CHECKED_SIZES: tuple[tuple[int, int], ...] = ((400, 300), (800, 600), (1200, 700), (2300, 900))

DEFAULT_NAME = "raschet.xlsx"


class ExportPricingWorkbookForm(BaseModel):
    """What the owner named when he asked for the workbook."""

    product_id: UUID | None = None
    category_id: UUID | None = None

    @model_validator(mode="after")
    def _something_is_named(self) -> "ExportPricingWorkbookForm":
        """Refuse a request naming neither: without both it is unknown whose dictionary to collect."""
        if self.product_id is None and self.category_id is None:
            msg = "The workbook needs a product or a category"
            raise ValueError(msg)
        return self


class PricingWorkbookFile(BaseModel):
    """The workbook itself and the name under which it is offered."""

    content: bytes
    name: str


@interactor
class ExportPricingWorkbook:
    """Interactor for collecting the pricing workbook out of the live catalogue."""

    product_gateway: ProductGateway
    category_gateway: CategoryGateway
    attribute_gateway: AttributeGateway
    pricing_settings_gateway: PricingSettingsGateway
    renderer: PricingWorkbookRenderer

    async def execute(self, data: ExportPricingWorkbookForm) -> PricingWorkbookFile:
        """Collect the workbook of one section, with the named product as its defaults."""
        logger.debug("Collecting the pricing workbook", product_id=data.product_id, category_id=data.category_id)
        product = await self._product(data.product_id)
        category_id = product.category_id if product is not None else await self._category(data.category_id)
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("The workbook was asked for before the settings were created")
            raise PricingSettingsNotFoundError

        attributes = tuple(
            attribute
            for attribute in await self.attribute_gateway.list_with_values()
            if attribute.category_id == category_id
        )
        source = PricingWorkbookSource(
            attributes=attributes,
            settings=settings,
            product=product,
            checks=_checked_sizes(product, attributes, settings),
        )
        return PricingWorkbookFile(
            content=self.renderer.render(source),
            name=f"raschet-{product.slug}.xlsx" if product is not None else DEFAULT_NAME,
        )

    async def _product(self, product_id: ProductId | None) -> Product | None:
        """Load the product whose markup becomes the defaults, or nothing when none was named."""
        if product_id is None:
            return None
        product = await self.product_gateway.get(product_id)
        if product is None:
            logger.warning("The workbook was asked for an unknown product", product_id=product_id)
            raise ProductNotFoundError
        return product

    async def _category(self, category_id: CategoryId | None) -> CategoryId:
        """Take the named section after making sure the catalogue still holds it."""
        if category_id is None or not await self.category_gateway.exists(category_id):
            logger.warning("The workbook was asked for an unknown category", category_id=category_id)
            raise CategoryNotFoundError
        return category_id


def _checked_sizes(
    product: Product | None,
    attributes: tuple[Attribute, ...],
    settings: PricingSettings,
) -> tuple[CheckedSize, ...]:
    """Price the sizes of the check sheet by the engine — the only implementation there is."""
    if product is None or not is_product_priceable(product, attributes):
        return ()
    return tuple(
        CheckedSize(dimensions=dimensions, quotation=_quotation(product, attributes, settings, dimensions))
        for dimensions in (
            Dimensions(width=Millimeters(value=width), height=Millimeters(value=height))
            for width, height in CHECKED_SIZES
        )
    )


def _quotation(
    product: Product,
    attributes: tuple[Attribute, ...],
    settings: PricingSettings,
    dimensions: Dimensions,
) -> Quotation | None:
    """Price one size of the check sheet, leaving a size the production bounds refuse without a total."""
    if not settings.is_within_limits(dimensions):
        return None
    return price_product(
        product=product,
        attributes=attributes,
        settings=settings,
        dimensions=dimensions,
        selections={},
    )
