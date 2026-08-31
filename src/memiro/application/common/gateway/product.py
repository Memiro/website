from abc import abstractmethod
from typing import Protocol

from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import ProductId


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
