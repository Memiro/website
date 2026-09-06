import structlog

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.manage_attributes.shared import AttributeRootForm, loaded_for_update
from memiro.entities.catalog.attribute.attribute_service import ensure_parents_are_usable
from memiro.entities.catalog.attribute.entity import ChangeAttributeData
from memiro.entities.common.identifiers import AttributeId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class ChangeAttributeForm(AttributeRootForm):
    """Owner-controlled root fields of the attribute being changed."""


@interactor
class ChangeAttribute:
    """Interactor for restating the root of one attribute."""

    uow: UoW
    attribute_gateway: AttributeGateway
    clock: Clock

    async def execute(self, attribute_id: AttributeId, data: ChangeAttributeForm) -> None:
        """Replace the root fields of one attribute and commit its transaction."""
        logger.debug("Changing an attribute", attribute_id=attribute_id)
        attribute = await loaded_for_update(self.attribute_gateway, attribute_id, command="change")
        dictionary = await self.attribute_gateway.list_with_values()
        ensure_parents_are_usable(
            data.parent_ids,
            attribute_id=attribute_id,
            category_id=attribute.category_id,
            dictionary=dictionary,
        )
        attribute.change(
            ChangeAttributeData(
                name=data.name,
                kind=data.kind,
                parent_ids=tuple(data.parent_ids),
                is_customer_changeable=data.is_customer_changeable,
                is_filterable=data.is_filterable,
                sort_order=data.sort_order,
            ),
            clock=self.clock,
        )
        await self.uow.commit()
        logger.info("Attribute changed", attribute_id=attribute_id)
