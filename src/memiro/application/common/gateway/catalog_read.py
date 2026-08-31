from abc import abstractmethod
from typing import Protocol

from memiro.application.browse_catalog.models import CategoryModel, ProductModel, ProductSummary


class CatalogReadGateway(Protocol):
    """Read storage port for public catalogue projections."""

    @abstractmethod
    async def list_categories(self) -> tuple[list[CategoryModel], int]:
        """List categories that have public products, with the total that match."""
        raise NotImplementedError

    @abstractmethod
    async def read_category(self, slug: str) -> CategoryModel | None:
        """Read a category by its slug, published products or not."""
        raise NotImplementedError

    @abstractmethod
    async def list_products_by_category(self, category_slug: str) -> tuple[list[ProductSummary], int]:
        """List public products of a category slug, with the total that match."""
        raise NotImplementedError

    @abstractmethod
    async def read_product(self, slug: str) -> ProductModel | None:
        """Read a public product card by its slug."""
        raise NotImplementedError
