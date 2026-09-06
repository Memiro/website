import structlog
from pydantic import BaseModel, Field

from memiro.application.common.gateway.attribute import AttributeGateway
from memiro.application.common.gateway.category import CategoryGateway
from memiro.application.common.input_limits import MAX_ATTRIBUTE_VALUES
from memiro.application.errors.catalog import CategoryNotFoundError
from memiro.application.manage_attributes.shared import AttributeRootForm, AttributeValueForm, as_value_data
from memiro.entities.catalog.attribute.attribute_service import ensure_parents_are_usable
from memiro.entities.catalog.attribute.entity import CreateAttributeData, attribute_factory
from memiro.entities.common.identifiers import AttributeId, CategoryId
from memiro_common.clock import Clock
from memiro_common.interactor import interactor
from memiro_common.logger import Logger
from memiro_common.uow import UoW

logger: Logger = structlog.get_logger(__name__)


class CreateAttributeForm(AttributeRootForm):
    """Owner-controlled fields of the attribute being created, dictionary included."""

    category_id: CategoryId
    # The rows of a new attribute carry no identifiers: there is nothing yet
    # for them to keep, and the aggregate issues every one of them itself.
    values: list[AttributeValueForm] = Field(
        default_factory=list[AttributeValueForm],
        max_length=MAX_ATTRIBUTE_VALUES,
    )


class CreatedAttribute(BaseModel):
    """Identifier of a newly created attribute."""

    id: AttributeId


@interactor
class CreateAttribute:
    """Interactor for adding one attribute with its dictionary to a category."""

    uow: UoW
    category_gateway: CategoryGateway
    attribute_gateway: AttributeGateway
    clock: Clock

    async def execute(self, data: CreateAttributeForm) -> CreatedAttribute:
        """Create an attribute with its dictionary and commit both in one transaction."""
        logger.debug("Creating an attribute", category_id=data.category_id)
        if not await self.category_gateway.exists(data.category_id):
            logger.warning("An attribute was created in an unknown category", category_id=data.category_id)
            raise CategoryNotFoundError
        dictionary = await self.attribute_gateway.list_with_values()
        ensure_parents_are_usable(
            data.parent_ids,
            attribute_id=None,
            category_id=data.category_id,
            dictionary=dictionary,
        )
        attribute = attribute_factory(
            CreateAttributeData(
                category_id=data.category_id,
                name=data.name,
                kind=data.kind,
                parent_ids=tuple(data.parent_ids),
                is_customer_changeable=data.is_customer_changeable,
                is_filterable=data.is_filterable,
                sort_order=data.sort_order,
                values=tuple(as_value_data(form) for form in data.values),
            ),
            clock=self.clock,
        )
        self.uow.add(attribute)
        await self.uow.commit()
        logger.info("Attribute created", attribute_id=attribute.id)
        return CreatedAttribute(id=attribute.id)
