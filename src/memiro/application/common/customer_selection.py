from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field, model_validator

from memiro.application.common.input_limits import MAX_QUANTITY
from memiro.application.errors.catalog import AttributeValueNotFoundError
from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import AttributeId
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class Selection(BaseModel):
    """One choice of the customer: what he put in place of the product's own value."""

    attribute_id: UUID
    value_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, ge=0, le=MAX_QUANTITY)

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
) -> dict[AttributeId, ChosenValue]:
    """Check every choice against the dictionary and the product, then index it by attribute.

    The customer *replaces* the product's own value, he does not introduce a
    setting the product never had: without something to replace, the add-on
    price would have nothing to be counted from (ADR-0007).
    """
    index = {attribute.id: attribute for attribute in attributes}
    values: dict[AttributeId, ChosenValue] = {}
    for selection in selections:
        attribute_id: AttributeId = selection.attribute_id
        attribute = index.get(attribute_id)
        declaration = product.declared(attribute_id)
        chosen = (
            attribute.configure(selection.value_id, selection.quantity)
            if attribute is not None and declaration is not None
            else None
        )
        if chosen is None:
            logger.warning(
                "A choice outside the product's dictionary",
                product_id=product.id,
                attribute_id=attribute_id,
                value_id=selection.value_id,
            )
            raise AttributeValueNotFoundError
        values[attribute_id] = chosen
    return values
