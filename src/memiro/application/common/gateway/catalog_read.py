from abc import abstractmethod
from collections.abc import Sequence
from typing import Protocol

from memiro.application.browse_catalog.models import CategoryModel, ProductModel, ProductSummary


class CatalogReadGateway(Protocol):
    """Read storage port for public catalogue projections."""

    @abstractmethod
    async def list_categories(self) -> Sequence[CategoryModel]:
        """List categories that have public products."""
        raise NotImplementedError

    @abstractmethod
    async def list_products(self, slug: str) -> tuple[bool, Sequence[ProductSummary]]:
        """List public products for a category slug."""
        raise NotImplementedError

    @abstractmethod
    async def read_product(self, slug: str) -> ProductModel | None:
        """Read a public product card by its slug."""
        raise NotImplementedError
