from typing import override
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.db.tables import (
    attribute_values_table,
    attributes_table,
    categories_table,
    product_declared_values_table,
    product_images_table,
    product_variants_table,
    products_table,
)
from memiro.application.browse_catalog.models import (
    CategoryModel,
    ProductAttribute,
    ProductAttributeValue,
    ProductModel,
    ProductSummary,
    ProductVariant,
    VariantOverride,
)
from memiro.application.common.gateway.catalog_read import CatalogReadGateway


class SACatalogReadGateway(CatalogReadGateway):
    """SQLAlchemy projections for the public catalogue."""

    def __init__(self, session: AsyncSession) -> None:
        """Keep the request-scoped session the projections execute through."""
        self._session = session

    @override
    async def list_categories(self) -> tuple[list[CategoryModel], int]:
        """Read the categories a published product hangs on, in the owner order."""
        published = exists(
            select(products_table.c.id).where(
                (products_table.c.category_id == categories_table.c.id) & products_table.c.is_published
            )
        )
        rows = (
            await self._session.execute(
                select(categories_table.c.name, categories_table.c.slug)
                .where(published)
                .order_by(categories_table.c.sort_order, categories_table.c.id)
            )
        ).all()
        categories = [CategoryModel(name=row.name, slug=row.slug) for row in rows]
        return categories, len(categories)

    @override
    async def read_category(self, slug: str) -> CategoryModel | None:
        """Resolve one category slug, whatever it holds."""
        row = (
            await self._session.execute(
                select(categories_table.c.name, categories_table.c.slug).where(categories_table.c.slug == slug)
            )
        ).one_or_none()
        return CategoryModel(name=row.name, slug=row.slug) if row is not None else None

    @override
    async def list_products_by_category(self, category_slug: str) -> tuple[list[ProductSummary], int]:
        """Read the published products of a category, each with its ordered image keys."""
        rows = (
            await self._session.execute(
                select(products_table.c.id, products_table.c.name, products_table.c.slug, products_table.c.price_from)
                .join(categories_table, products_table.c.category_id == categories_table.c.id)
                .where((categories_table.c.slug == category_slug) & products_table.c.is_published)
                .order_by(products_table.c.name, products_table.c.id)
            )
        ).all()
        products: list[ProductSummary] = []
        for row in rows:
            keys = (
                (
                    await self._session.execute(
                        select(product_images_table.c.key)
                        .where(product_images_table.c.product_id == row.id)
                        .order_by(product_images_table.c.sort_order)
                    )
                )
                .scalars()
                .all()
            )
            products.append(
                ProductSummary(
                    name=row.name,
                    slug=row.slug,
                    price_from=row.price_from.amount if row.price_from else None,
                    image_keys=list(keys),
                )
            )
        return products, len(products)

    @override
    async def read_product(self, slug: str) -> ProductModel | None:
        """Read the published product row, then its images, variants and declared values."""
        row = (
            (
                await self._session.execute(
                    select(products_table).where((products_table.c.slug == slug) & products_table.c.is_published)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        images = (
            (
                await self._session.execute(
                    select(product_images_table.c.key)
                    .where(product_images_table.c.product_id == row["id"])
                    .order_by(product_images_table.c.sort_order)
                )
            )
            .scalars()
            .all()
        )
        variants = (
            await self._session.execute(
                select(
                    product_variants_table.c.width_mm,
                    product_variants_table.c.height_mm,
                    product_variants_table.c.price,
                    product_variants_table.c.overrides,
                )
                .where(product_variants_table.c.product_id == row["id"])
                .order_by(product_variants_table.c.sort_order)
            )
        ).all()
        declared = (
            await self._session.execute(
                select(
                    attributes_table.c.id,
                    attributes_table.c.name,
                    attribute_values_table.c.id.label("value_id"),
                    attribute_values_table.c.name.label("value_name"),
                    attribute_values_table.c.sort_order.label("value_sort_order"),
                )
                .select_from(
                    product_declared_values_table.join(
                        attributes_table,
                        product_declared_values_table.c.attribute_id == attributes_table.c.id,
                    ).join(
                        attribute_values_table,
                        attribute_values_table.c.attribute_id == attributes_table.c.id,
                    )
                )
                .where(product_declared_values_table.c.product_id == row["id"])
                .order_by(attributes_table.c.sort_order, attribute_values_table.c.sort_order)
            )
        ).all()
        attributes: dict[UUID, ProductAttribute] = {}
        for item in declared:
            attribute = attributes.setdefault(
                item.id,
                ProductAttribute(id=item.id, name=item.name, values=[]),
            )
            attribute.values.append(ProductAttributeValue(id=item.value_id, name=item.value_name, quantity=None))
        return ProductModel(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            description=row["description"],
            price_from=row["price_from"].amount if row["price_from"] else None,
            image_keys=list(images),
            attributes=list(attributes.values()),
            variants=[
                ProductVariant(
                    width_mm=item.width_mm.value,
                    height_mm=item.height_mm.value,
                    price=item.price.amount,
                    overrides=[
                        VariantOverride(
                            attribute_id=value.attribute_id,
                            value_id=value.chosen.value_id,
                            quantity=value.chosen.quantity,
                        )
                        for value in item.overrides
                    ],
                )
                for item in variants
            ],
        )
