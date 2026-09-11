from collections.abc import Sequence
from typing import Any, override
from uuid import UUID

from sqlalchemy import ColumnElement, Row, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from memiro.adapters.db.tables import (
    attribute_values_table,
    attributes_table,
    categories_table,
    landing_conditions_table,
    landings_table,
    product_declared_values_table,
    product_images_table,
    product_variants_table,
    products_table,
    works_table,
)
from memiro.application.browse_catalog.models import (
    PAGE_SIZE,
    CatalogQuery,
    CatalogSort,
    CategoryModel,
    FilterGroup,
    FilterOption,
    LandingModel,
    LandingSummary,
    PriceBounds,
    ProductAttribute,
    ProductAttributeValue,
    ProductModel,
    ProductSummary,
    ProductVariant,
    VariantOverride,
    WorkModel,
    WorkProduct,
)
from memiro.application.common.gateway.catalog_read import CatalogReadGateway
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.common.money import Money


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
                select(categories_table.c.name, categories_table.c.slug, categories_table.c.updated_at)
                .where(published)
                .order_by(categories_table.c.sort_order, categories_table.c.id)
            )
        ).all()
        categories = [CategoryModel(name=row.name, slug=row.slug, updated_at=row.updated_at) for row in rows]
        return categories, len(categories)

    @override
    async def read_category(self, slug: str) -> CategoryModel | None:
        """Resolve one category slug, whatever it holds."""
        row = (
            await self._session.execute(
                select(categories_table.c.name, categories_table.c.slug, categories_table.c.updated_at).where(
                    categories_table.c.slug == slug
                )
            )
        ).one_or_none()
        return CategoryModel(name=row.name, slug=row.slug, updated_at=row.updated_at) if row is not None else None

    @override
    async def list_products_by_category(
        self,
        category_slug: str,
        query: CatalogQuery,
    ) -> tuple[list[ProductSummary], int]:
        """Read one page of the published products the query leaves, each with its ordered image keys."""
        rows = await self._filterable_rows(category_slug)
        conditions = self._conditions(category_slug, query, self._selected(rows, query))
        total = (
            await self._session.execute(select(func.count()).select_from(products_table).where(*conditions))
        ).scalar_one()
        listing = (
            await self._session.execute(
                select(
                    products_table.c.id,
                    products_table.c.name,
                    products_table.c.slug,
                    products_table.c.price_from,
                    products_table.c.updated_at,
                )
                .where(*conditions)
                .order_by(*self._ordering(query.sort))
                .limit(PAGE_SIZE)
                .offset((query.page - 1) * PAGE_SIZE)
            )
        ).all()
        products: list[ProductSummary] = []
        for row in listing:
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
                    updated_at=row.updated_at,
                )
            )
        return products, total

    @override
    async def filter_groups(self, category_slug: str, query: CatalogQuery) -> list[FilterGroup]:
        """Count every row of every filterable attribute under the other groups and the price range."""
        rows = await self._filterable_rows(category_slug)
        selected = self._selected(rows, query)
        groups: list[FilterGroup] = []
        for attribute_id in dict.fromkeys(row.attribute_id for row in rows):
            # An option counts what it would leave, so its own group's choice
            # must not narrow it (the counters stay usable after a click).
            conditions = self._conditions(category_slug, query, selected, ignoring=attribute_id)
            counted: dict[UUID, int] = {
                row.value_id: row.matching
                for row in (
                    await self._session.execute(
                        select(
                            product_declared_values_table.c.value_id,
                            func.count(products_table.c.id).label("matching"),
                        )
                        .select_from(
                            products_table.join(
                                product_declared_values_table,
                                product_declared_values_table.c.product_id == products_table.c.id,
                            )
                        )
                        .where(*conditions, product_declared_values_table.c.attribute_id == attribute_id)
                        .group_by(product_declared_values_table.c.value_id)
                    )
                ).all()
            }
            options = [
                FilterOption(
                    value_id=row.value_id,
                    name=row.value_name,
                    count=counted.get(row.value_id, 0),
                    is_selected=row.value_id in selected.get(attribute_id, ()),
                )
                for row in rows
                if row.attribute_id == attribute_id
            ]
            name = next(row.attribute_name for row in rows if row.attribute_id == attribute_id)
            groups.append(FilterGroup(attribute_id=attribute_id, name=name, options=options))
        return groups

    @override
    async def price_bounds(self, category_slug: str, query: CatalogQuery) -> PriceBounds:
        """Read the price range of the whole published category — the hint the visitor types inside."""
        row = (
            await self._session.execute(
                select(func.min(products_table.c.price_from), func.max(products_table.c.price_from))
                .select_from(
                    products_table.join(categories_table, products_table.c.category_id == categories_table.c.id)
                )
                .where((categories_table.c.slug == category_slug) & products_table.c.is_published)
            )
        ).one()
        lowest, highest = row
        return PriceBounds(
            lowest=lowest.amount if lowest else None,
            highest=highest.amount if highest else None,
            selected_min=query.price_min,
            selected_max=query.price_max,
        )

    @override
    async def list_landings(self) -> tuple[list[LandingSummary], int]:
        """Read the published landings in the owner's order."""
        rows = (
            await self._session.execute(
                select(landings_table.c.slug, landings_table.c.heading, landings_table.c.updated_at)
                .where(landings_table.c.is_published)
                .order_by(landings_table.c.sort_order, landings_table.c.id)
            )
        ).all()
        landings = [LandingSummary(slug=row.slug, heading=row.heading, updated_at=row.updated_at) for row in rows]
        return landings, len(landings)

    @override
    async def list_works(self) -> tuple[list[WorkModel], int]:
        """Read the published works in the owner's order, each with the address of its published mirror."""
        rows = (
            await self._session.execute(
                select(
                    works_table.c.photo_key,
                    works_table.c.title,
                    works_table.c.description,
                    products_table.c.slug.label("product_slug"),
                    categories_table.c.slug.label("category_slug"),
                )
                .select_from(works_table)
                .outerjoin(
                    products_table.join(categories_table, products_table.c.category_id == categories_table.c.id),
                    (works_table.c.product_id == products_table.c.id) & products_table.c.is_published,
                )
                .where(works_table.c.is_published)
                .order_by(works_table.c.sort_order, works_table.c.id)
            )
        ).all()
        works = [
            WorkModel(
                photo_key=row.photo_key,
                title=row.title,
                description=row.description,
                product=(
                    None
                    if row.product_slug is None
                    else WorkProduct(category_slug=row.category_slug, slug=row.product_slug)
                ),
            )
            for row in rows
        ]
        return works, len(works)

    @override
    async def read_landing(self, slug: str) -> LandingModel | None:
        """Read one published landing with its category and the values it narrows by."""
        row = (
            (
                await self._session.execute(
                    select(landings_table, categories_table.c.slug.label("category_slug"), categories_table.c.name)
                    .join(categories_table, landings_table.c.category_id == categories_table.c.id)
                    .where((landings_table.c.slug == slug) & landings_table.c.is_published)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        conditions = (
            await self._session.execute(
                select(landing_conditions_table.c.value_id, attributes_table.c.is_filterable)
                .join(attributes_table, attributes_table.c.id == landing_conditions_table.c.attribute_id)
                .where(landing_conditions_table.c.landing_id == row["id"])
            )
        ).all()
        # The landing narrows by the rule of the sidebar and has no second
        # implementation of it: a condition the sidebar would drop would leave
        # an indexable page showing the whole category under a narrowing
        # heading (ADR-0003), so the page is not published at all.
        if any(not condition.is_filterable for condition in conditions):
            return None
        return LandingModel(
            slug=row["slug"],
            heading=row["heading"],
            updated_at=row["updated_at"],
            title=row["title"],
            description=row["description"],
            text=row["text"],
            category_slug=row["category_slug"],
            category_name=row["name"],
            values=[condition.value_id for condition in conditions],
        )

    @override
    async def read_product(self, slug: str) -> ProductModel | None:
        """Read the published product row, then its images, variants and declared values."""
        row = (
            (
                await self._session.execute(
                    select(
                        products_table,
                        categories_table.c.slug.label("category_slug"),
                        categories_table.c.name.label("category_name"),
                    )
                    .join(categories_table, products_table.c.category_id == categories_table.c.id)
                    .where((products_table.c.slug == slug) & products_table.c.is_published)
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
                    attributes_table.c.kind,
                    attributes_table.c.is_customer_changeable,
                    attribute_values_table.c.id.label("value_id"),
                    attribute_values_table.c.name.label("value_name"),
                    attribute_values_table.c.sort_order.label("value_sort_order"),
                    product_declared_values_table.c.value_id.label("declared_value_id"),
                    product_declared_values_table.c.quantity.label("declared_quantity"),
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
                ProductAttribute(
                    id=item.id,
                    name=item.name,
                    kind=item.kind,
                    declared_value_id=item.declared_value_id,
                    is_customer_changeable=item.is_customer_changeable,
                    values=[],
                ),
            )
            # The single row of a numeric attribute is its tariff, not an
            # option to pick.
            attribute.values.append(
                ProductAttributeValue(id=None, name=item.value_name, quantity=item.declared_quantity)
                if item.kind is AttributeKind.NUMBER
                else ProductAttributeValue(id=item.value_id, name=item.value_name, quantity=None)
            )
        return ProductModel(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            category_slug=row["category_slug"],
            category_name=row["category_name"],
            description=row["description"],
            price_from=row["price_from"].amount if row["price_from"] else None,
            image_keys=list(images),
            updated_at=row["updated_at"],
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

    async def _filterable_rows(self, category_slug: str) -> Sequence[Row[Any]]:
        """Read the rows of the attributes a visitor may narrow this category by, in the owner's order."""
        return (
            await self._session.execute(
                select(
                    attributes_table.c.id.label("attribute_id"),
                    attributes_table.c.name.label("attribute_name"),
                    attribute_values_table.c.id.label("value_id"),
                    attribute_values_table.c.name.label("value_name"),
                )
                .select_from(
                    attributes_table.join(
                        categories_table, attributes_table.c.category_id == categories_table.c.id
                    ).join(
                        attribute_values_table,
                        attribute_values_table.c.attribute_id == attributes_table.c.id,
                    )
                )
                .where(
                    (categories_table.c.slug == category_slug)
                    # A numeric attribute is typed, not picked, so it gives
                    # no filter; the rest is the owner's own switch.
                    & (attributes_table.c.kind == AttributeKind.SELECT)
                    & attributes_table.c.is_filterable
                )
                .order_by(
                    attributes_table.c.sort_order,
                    attributes_table.c.id,
                    attribute_values_table.c.sort_order,
                    attribute_values_table.c.id,
                )
            )
        ).all()

    @staticmethod
    def _selected(rows: Sequence[Row[Any]], query: CatalogQuery) -> dict[UUID, list[UUID]]:
        """Group the asked values by their attribute, dropping what this category does not offer."""
        owner: dict[UUID, UUID] = {row.value_id: row.attribute_id for row in rows}
        selected: dict[UUID, list[UUID]] = {}
        for value_id in query.values:
            attribute_id = owner.get(value_id)
            if attribute_id is not None:
                selected.setdefault(attribute_id, []).append(value_id)
        return selected

    @staticmethod
    def _conditions(
        category_slug: str,
        query: CatalogQuery,
        selected: dict[UUID, list[UUID]],
        *,
        ignoring: UUID | None = None,
    ) -> list[ColumnElement[bool]]:
        """Build what narrows a category listing: its slug, publication, the chosen values and the price."""
        conditions: list[ColumnElement[bool]] = [
            products_table.c.category_id.in_(
                select(categories_table.c.id).where(categories_table.c.slug == category_slug)
            ),
            products_table.c.is_published,
        ]
        for attribute_id, values in selected.items():
            if attribute_id == ignoring:
                continue
            # An alias per condition: the counting query already selects from
            # the declarations table, and an uncorrelated copy of it would be
            # auto-correlated away.
            declared = product_declared_values_table.alias()
            conditions.append(
                exists(
                    select(declared.c.product_id).where(
                        (declared.c.product_id == products_table.c.id)
                        & (declared.c.attribute_id == attribute_id)
                        & declared.c.value_id.in_(values)
                    )
                )
            )
        if query.price_min is not None:
            conditions.append(products_table.c.price_from >= Money(amount=query.price_min))
        if query.price_max is not None:
            conditions.append(products_table.c.price_from <= Money(amount=query.price_max))
        return conditions

    @staticmethod
    def _ordering(sort: CatalogSort) -> tuple[ColumnElement[object], ...]:
        """Put the listing in the order the visitor asked for; a product without a price goes last."""
        if sort is CatalogSort.CHEAPEST:
            return (products_table.c.price_from.asc().nulls_last(), products_table.c.name, products_table.c.id)
        if sort is CatalogSort.DEAREST:
            return (products_table.c.price_from.desc().nulls_last(), products_table.c.name, products_table.c.id)
        return (products_table.c.name, products_table.c.id)
