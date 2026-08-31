from typing import override

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memiro.adapters.db.errors import LockTimeoutError
from memiro.adapters.db.tables import products_table
from memiro.application.common.gateway.product import ProductGateway
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import ProductId

# Postgres reports a lock wait cut short by ``lock_timeout`` as lock_not_available.
LOCK_NOT_AVAILABLE = "55P03"


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
                selectinload(Product._declared_values),  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
            )
        )
        if eager_variants:
            statement = statement.options(selectinload(Product._variants))  # type: ignore[arg-type]  # noqa: SLF001  # pyright: ignore[reportArgumentType,reportPrivateUsage]
        if for_update:
            statement = statement.with_for_update()
        try:
            result = await self._session.execute(statement)
        except DBAPIError as error:
            # A refused lock is a lost race, not a defect: the caller is told
            # to retry (429), while every other driver failure stays a 500.
            # The asyncpg dialect re-wraps the driver exception in its own
            # class, so the SQLSTATE it copies over is the only thing left to
            # recognise a refused lock by.
            if getattr(error.orig, "sqlstate", None) != LOCK_NOT_AVAILABLE:
                raise
            raise LockTimeoutError from error
        return result.scalar_one_or_none()
