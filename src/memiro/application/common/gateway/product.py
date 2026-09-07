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
    async def slug_owner(self, slug: str) -> ProductId | None:
        """Name the product holding this public address, or ``None`` if it is free.

        Uniqueness belongs to the transaction, not to the aggregate: a
        product cannot see the addresses of the others, and the database is
        the only place that knows them all.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_by_ids(self, product_ids: Sequence[ProductId]) -> Sequence[Product]:
        """Load these products with their declared values, silently skipping the ones that are gone.

        One page of the owner's list is one question: a product per query
        would put the length of the page into the number of round trips.
        """
        raise NotImplementedError

    @abstractmethod
    async def all_ids(self) -> Sequence[ProductId]:
        """List the identifier of every product, in one stable order.

        The whole catalogue is what repricing walks: it takes no shortcut
        through the products a change could have touched (ADR-0014).
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
