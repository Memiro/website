from collections.abc import Sequence
from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memiro.adapters.db.tables import attributes_table, products_table
from memiro.application.common.gateway.catalog import AttributeGateway, ProductGateway
from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import ProductId


class SAProductGateway(ProductGateway):
    """SQLAlchemy-based implementation of ``ProductGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def get(
        self,
        product_id: ProductId,
        *,
        for_update: bool = False,
        eager_variants: bool = False,
    ) -> Product | None:
        """Load declared values and optionally the locked variant collection."""
        statement = (
            select(Product)
            .where(products_table.c.id == product_id)
            .options(
                # Imperative mapping leaves the instrumented attributes invisible
                # to the type checkers; both relationships exist at runtime.
                selectinload(Product.declared_values),  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
            )
        )
        if eager_variants:
            statement = statement.options(selectinload(Product._variants))  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()


class SAAttributeGateway(AttributeGateway):
    """SQLAlchemy-based implementation of ``AttributeGateway``."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the gateway queries through."""
        self._session = session

    @override
    async def list_with_values(self) -> Sequence[Attribute]:
        """Load the whole dictionary, each attribute with its values in the owner's order."""
        result = await self._session.execute(
            select(Attribute).order_by(attributes_table.c.sort_order).options(selectinload(Attribute.values)),  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        )
        return result.scalars().all()
