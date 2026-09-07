from collections.abc import Collection, Sequence
from typing import override

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memiro.adapters.db.errors import LOCK_NOT_AVAILABLE, LockTimeoutError, sqlstate_of
from memiro.adapters.db.tables import product_declared_values_table, products_table
from memiro.application.common.gateway.product import ProductGateway
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, ProductId


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
        eager_images: bool = False,
    ) -> Product | None:
        """Load declared values and optionally the child collections a command is about to touch."""
        statement = (
            select(Product)
            .where(products_table.c.id == product_id)
            .options(
                # Imperative mapping leaves the instrumented attributes invisible
                # to the type checkers; both relationships exist at runtime.
                selectinload(Product._declared_values),  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
            )
        )
        if eager_variants:
            statement = statement.options(selectinload(Product._variants))  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
        if eager_images:
            statement = statement.options(selectinload(Product._images))  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
        if for_update:
            statement = statement.with_for_update()
        try:
            result = await self._session.execute(statement)
        except DBAPIError as error:
            # A refused lock is a lost race, not a defect: the caller is told
            # to retry (429), while every other driver failure stays a 500.
            if sqlstate_of(error) != LOCK_NOT_AVAILABLE:
                raise
            raise LockTimeoutError from error
        return result.scalar_one_or_none()

    @override
    async def slug_owner(self, slug: str) -> ProductId | None:
        """Ask the unique column who holds the address: no aggregate is needed to answer that."""
        result = await self._session.execute(
            select(products_table.c.id).where(products_table.c.slug == slug),
        )
        return result.scalar_one_or_none()

    @override
    async def list_by_ids(self, product_ids: Sequence[ProductId]) -> Sequence[Product]:
        """Read one page of products with their declarations in a single statement."""
        if not product_ids:
            return ()
        result = await self._session.execute(
            select(Product)
            .where(products_table.c.id.in_(product_ids))
            .options(
                selectinload(Product._declared_values),  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
            ),
        )
        return result.scalars().all()

    @override
    async def all_ids(self) -> Sequence[ProductId]:
        """Read the identifiers of the whole catalogue in the one order that cannot repeat itself."""
        result = await self._session.execute(select(products_table.c.id).order_by(products_table.c.id))
        return result.scalars().all()

    @override
    async def names_declaring_values(self, value_ids: Collection[AttributeValueId]) -> Sequence[str]:
        """Read the names behind the declarations of these dictionary rows."""
        if not value_ids:
            return ()
        return await self._names_declaring(product_declared_values_table.c.value_id.in_(value_ids))

    @override
    async def names_declaring_attribute(self, attribute_id: AttributeId) -> Sequence[str]:
        """Read the names behind every declaration made on this attribute."""
        return await self._names_declaring(product_declared_values_table.c.attribute_id == attribute_id)

    async def _names_declaring(self, condition: ColumnElement[bool]) -> Sequence[str]:
        """Name the products a declaration condition matches, once each and in one order."""
        result = await self._session.execute(
            select(products_table.c.name)
            .join(
                product_declared_values_table,
                product_declared_values_table.c.product_id == products_table.c.id,
            )
            .where(condition)
            .distinct()
            .order_by(products_table.c.name),
        )
        return result.scalars().all()
