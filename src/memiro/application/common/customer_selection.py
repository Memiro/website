from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import BaseModel, model_validator

from memiro.application.errors.catalog import AttributeValueNotFoundError
from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind
from memiro.entities.catalog.product.entity import ConfiguredValue, Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class Selection(BaseModel):
    """One choice of the customer: what he put in place of the product's own value."""

    attribute_id: UUID
    value_id: UUID | None = None
    quantity: Decimal | None = None

    @model_validator(mode="after")
    def _one_representation(self) -> "Selection":
        """Require a dictionary row or a numeric quantity, but never both."""
        if (self.value_id is None) is (self.quantity is None):
            msg = "A selection must name exactly one of value_id and quantity"
            raise ValueError(msg)
        return self


def customer_selections(
    product: Product,
    attributes: Sequence[Attribute],
    selections: Sequence[Selection],
) -> dict[AttributeId, ConfiguredValue]:
    """Check every choice against the dictionary and the product, then index it by attribute.

    The customer *replaces* the product's own value, he does not introduce a
    setting the product never had: without something to replace, the add-on
    price would have nothing to be counted from (ADR-0007).
    """
    index = {attribute.id: attribute for attribute in attributes}
    chosen: dict[AttributeId, ConfiguredValue] = {}
    for selection in selections:
        attribute_id: AttributeId = selection.attribute_id
        attribute = index.get(attribute_id)
        declaration = product.declared(attribute_id)
        configured: ConfiguredValue | None = None
        if attribute is not None and declaration is not None:
            value_id: AttributeValueId | None = selection.value_id
            if (
                attribute.kind is AttributeKind.SELECT
                and value_id is not None
                and attribute.value(value_id) is not None
            ):
                configured = ConfiguredValue(value_id=value_id, quantity=None)
            elif attribute.kind is AttributeKind.NUMBER and selection.quantity is not None:
                configured = ConfiguredValue(value_id=None, quantity=selection.quantity)
        if configured is None:
            logger.warning(
                "A choice outside the product's dictionary",
                product_id=product.id,
                attribute_id=attribute_id,
                value_id=selection.value_id,
            )
            raise AttributeValueNotFoundError
        chosen[attribute_id] = configured
    return chosen
