import structlog

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.landing import LandingGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.errors.catalog import AttributeInUseError
from memiro.application.manage_attributes.shared import loaded_for_update
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
    landing_gateway: LandingGateway
    product_gateway: ProductGateway

    async def execute(self, attribute_id: AttributeId) -> None:
        """Remove one attribute nothing depends on and commit its transaction."""
        logger.debug("Removing an attribute", attribute_id=attribute_id)
        attribute = await loaded_for_update(self.attribute_gateway, attribute_id, command="remove")
        dictionary = await self.attribute_gateway.list_with_values()
        dependents = names_depending_on(attribute_id, dictionary=dictionary)
        products = await self.product_gateway.names_declaring_attribute(attribute_id)
        landings = await self.landing_gateway.headings_narrowing_by_attribute(attribute_id)
        if products or dependents or landings:
            # One refusal for one question — "who still needs it" — so the
            # owner reads a single list instead of two codes for one wall.
            logger.warning(
                "An attribute still in use was removed",
                attribute_id=attribute_id,
                product_count=len(products),
                dependent_count=len(dependents),
                landing_count=len(landings),
            )
            raise AttributeInUseError(
                products=tuple(products),
                attributes=dependents,
                landings=tuple(landings),
            )
        await self.uow.delete(attribute)
        await self.uow.commit()
        logger.info("Attribute removed", attribute_id=attribute_id)
