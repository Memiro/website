import structlog

from memiro.application.common.event import EventBus, TariffChanged
from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.landing import LandingGateway
from memiro.application.common.gateway.product import ProductGateway
from memiro.application.errors.catalog import AttributeValueInUseError
from memiro.application.manage_attributes.shared import ValueSetForm, as_replacements, loaded_for_update
from memiro.entities.common.identifiers import AttributeId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class ReplaceValuesForm(ValueSetForm):
    """The dictionary of one attribute as the owner wants it to end up."""


@interactor
class ReplaceValues:
    """Interactor for replacing the whole dictionary of one attribute."""

    uow: UoW
    attribute_gateway: AttributeGateway
    landing_gateway: LandingGateway
    product_gateway: ProductGateway
    event_bus: EventBus
    clock: Clock

    async def execute(self, attribute_id: AttributeId, data: ReplaceValuesForm) -> None:
        """Replace the values of one attribute and commit its transaction."""
        logger.debug("Replacing the values of an attribute", attribute_id=attribute_id)
        attribute = await loaded_for_update(self.attribute_gateway, attribute_id, command="replace_values")
        values = as_replacements(data.values)
        # The refusal is owed before the delete reaches storage: ``CASCADE`` on
        # the referencing rows exists to clean up after a legal removal, not to
        # decide whether one is legal.
        removed = attribute.values_absent_from(values)
        products = await self.product_gateway.names_declaring_values(removed)
        landings = await self.landing_gateway.headings_narrowing_by_values(removed)
        if products or landings:
            logger.warning(
                "A declared dictionary value was removed",
                attribute_id=attribute_id,
                product_count=len(products),
                landing_count=len(landings),
            )
            raise AttributeValueInUseError(products=tuple(products), landings=tuple(landings))
        attribute.replace_values(values, clock=self.clock)
        await self.uow.commit()
        await self.event_bus.publish(TariffChanged(attribute_id=attribute_id))
        logger.info("Attribute values replaced", attribute_id=attribute_id, value_count=len(values))
