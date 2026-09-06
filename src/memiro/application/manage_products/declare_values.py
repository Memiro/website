from __future__ import annotations

import structlog
from pydantic import BaseModel, Field, model_validator

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.common.input_limits import MAX_SELECTIONS
from memiro.application.manage_products.shared import DeclarationForm, declarations, loaded_for_update
from memiro.entities.common.identifiers import ProductId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

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
    clock: Clock

    async def execute(self, product_id: ProductId, data: DeclareValuesForm) -> None:
        """Replace the whole declared set of one product and commit its transaction."""
        logger.debug("Declaring product values", product_id=product_id)
        product = await loaded_for_update(self.product_gateway, product_id, command="declare_values")
        attributes = await self.attribute_gateway.list_with_values()
        product.declare_values(declarations(product, attributes, data.declarations), clock=self.clock)
        await self.uow.commit()
        logger.info("Product values declared", product_id=product_id, count=len(data.declarations))
