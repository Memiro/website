from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field, model_validator

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.pricing import PricingSettingsGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import MAX_SELECTIONS
from memiro.application.common.variant_pricing import repriced_variants
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.application.manage_products.shared import DeclarationForm, as_declarations, loaded_for_update
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

if TYPE_CHECKING:
    from memiro.entities.catalog.attribute.entity import Attribute
    from memiro.entities.catalog.product.entity import Product

logger: Logger = structlog.get_logger(__name__)


class DeclareValuesForm(BaseModel):
    """Everything the product declares by the attributes of its section, as the owner wants it to end up."""

    declarations: list[DeclarationForm] = Field(
        default_factory=list[DeclarationForm],
        max_length=MAX_SELECTIONS,
    )

    @model_validator(mode="after")
    def _one_declaration_per_attribute(self) -> DeclareValuesForm:
        """Refuse two declarations that would compete for one attribute of the section."""
        attribute_ids = [declaration.attribute_id for declaration in self.declarations]
        if len(set(attribute_ids)) != len(attribute_ids):
            msg = "A product declares one value per attribute"
            raise ValueError(msg)
        return self


@interactor
class DeclareValues:
    """Interactor for restating what a product declares on the attributes of its section."""

    uow: UoW
    product_gateway: ProductGateway
    attribute_gateway: AttributeGateway
    pricing_settings_gateway: PricingSettingsGateway
    clock: Clock

    async def execute(self, product_id: ProductId, data: DeclareValuesForm) -> None:
        """Replace the whole declared set of one product and commit its transaction."""
        logger.debug("Declaring product values", product_id=product_id)
        product = await loaded_for_update(self.product_gateway, product_id, command="declare_values")
        attributes = await self.attribute_gateway.list_with_values()
        product.declare_values(as_declarations(product, attributes, data.declarations), clock=self.clock)
        await self._repriced(product, attributes)
        await self.uow.commit()
        logger.info("Product values declared", product_id=product_id, count=len(data.declarations))

    async def _repriced(self, product: Product, attributes: Sequence[Attribute]) -> None:
        """Bring the precalculated variants to the values just declared: they are half of their price."""
        # Asked only of a product that has variants: there is nothing to
        # reprice without them, and a refusal for the owner who has not
        # reached the calculation yet would be one he cannot act on.
        if not product.variants:
            return
        settings = await self.pricing_settings_gateway.get_with_surcharges()
        if settings is None:
            logger.warning("Values were declared before pricing setup", product_id=product.id)
            raise PricingSettingsNotFoundError
        repriced_variants(product, attributes=attributes, settings=settings, clock=self.clock)
