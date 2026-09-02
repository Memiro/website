import structlog

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.errors.catalog import AttributeInUseError, AttributeNotFoundError
from memiro.entities.catalog.attribute.attribute_service import names_depending_on
from memiro.entities.common.identifiers import AttributeId
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


@interactor
class RemoveAttribute:
    """Interactor for removing one attribute together with its dictionary."""

    uow: UoW
    attribute_gateway: AttributeGateway
    product_gateway: ProductGateway

    async def execute(self, attribute_id: AttributeId) -> None:
        """Remove one attribute nothing depends on and commit its transaction."""
        logger.debug("Removing an attribute", attribute_id=attribute_id)
        attribute = await self.attribute_gateway.get(attribute_id, for_update=True)
        if attribute is None:
            logger.warning("An unknown attribute was removed", attribute_id=attribute_id)
            raise AttributeNotFoundError
        dependents = names_depending_on(
            attribute_id,
            dictionary=await self.attribute_gateway.list_with_values(),
        )
        products = await self.product_gateway.names_declaring_attribute(attribute_id)
        if products or dependents:
            # One refusal for one question — "who still needs it" — so the
            # owner reads a single list instead of two codes for one wall.
            logger.warning(
                "An attribute still in use was removed",
                attribute_id=attribute_id,
                product_count=len(products),
                dependent_count=len(dependents),
            )
            raise AttributeInUseError(products=tuple(products), attributes=dependents)
        await self.uow.delete(attribute)
        await self.uow.commit()
        logger.info("Attribute removed", attribute_id=attribute_id)
