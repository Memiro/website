from abc import abstractmethod
from collections.abc import Collection, Sequence
from typing import Protocol

from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, ProductId


class ProductGateway(Protocol):
    """Storage port of the ``Product`` aggregate."""

    @abstractmethod
    async def get(
        self,
        product_id: ProductId,
        *,
        for_update: bool = False,
        eager_variants: bool = False,
    ) -> Product | None:
        """Load a product with its declared values, or ``None`` if there is no such product.

        Implementations must load the declared values eagerly: pricing reads
        them for every request, and a lazy load behind the gateway is
        forbidden. ``eager_variants`` loads the private child collection for
        management commands; ``for_update`` locks the aggregate root until
        the current transaction ends.
        """
        raise NotImplementedError

    @abstractmethod
    async def names_declaring_values(self, value_ids: Collection[AttributeValueId]) -> Sequence[str]:
        """Name the products that declare any of these dictionary rows.

        Implementations return distinct names in one stable order: the answer
        is shown to the owner as the reason a row cannot leave the dictionary.
        """
        raise NotImplementedError

    @abstractmethod
    async def names_declaring_attribute(self, attribute_id: AttributeId) -> Sequence[str]:
        """Name the products that declare anything on this attribute, in one stable order."""
        raise NotImplementedError
