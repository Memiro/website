from abc import abstractmethod
from typing import Protocol

from memiro.application.browse_catalog.models import (
    CatalogQuery,
    CategoryModel,
    FilterGroup,
    LandingModel,
    LandingSummary,
    PriceBounds,
    ProductModel,
    ProductSummary,
)


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
    async def list_products_by_category(
        self,
        category_slug: str,
        query: CatalogQuery,
    ) -> tuple[list[ProductSummary], int]:
        """List one page of the public products the query leaves, with the total that match."""
        raise NotImplementedError

    @abstractmethod
    async def filter_groups(self, category_slug: str, query: CatalogQuery) -> list[FilterGroup]:
        """Build the filter groups of a category, each option counted under the other groups."""
        raise NotImplementedError

    @abstractmethod
    async def price_bounds(self, category_slug: str, query: CatalogQuery) -> PriceBounds:
        """Read the cheapest and the dearest published product of the whole category."""
        raise NotImplementedError

    @abstractmethod
    async def list_landings(self) -> tuple[list[LandingSummary], int]:
        """List the published landings in the owner's order, with the total that match."""
        raise NotImplementedError

    @abstractmethod
    async def read_landing(self, slug: str) -> LandingModel | None:
        """Read one published landing with the values it narrows its category by."""
        raise NotImplementedError

    @abstractmethod
    async def read_product(self, slug: str) -> ProductModel | None:
        """Read a public product card by its slug."""
        raise NotImplementedError
