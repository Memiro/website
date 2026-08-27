"""Direct writes that stand in for the admin write path (§14.5.5).

There is no use case that creates a product, an attribute or the pricing
settings yet — the admin brings them with its own slice — so the arrangement
of a pricing test goes straight to the tables through named helpers.
"""

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.tables import (
    attribute_values_table,
    attributes_table,
    pricing_settings_table,
    product_declared_values_table,
    products_table,
)
from tests.common.factory.catalog import ALUMINIUM, BLADE, PRODUCT, demo_attributes, demo_product, demo_settings


async def prime_dictionary(engine: AsyncEngine) -> None:
    """Insert the demo dictionary and the canonical product it describes."""
    attributes = demo_attributes()
    product = demo_product()
    async with engine.begin() as connection:
        await connection.execute(
            insert(attributes_table),
            [
                {"id": attribute.id, "name": attribute.name, "sort_order": attribute.sort_order}
                for attribute in attributes
            ],
        )
        await connection.execute(
            insert(attribute_values_table),
            [
                {
                    "id": value.id,
                    "attribute_id": attribute.id,
                    "name": value.name,
                    "rate_amount": value.rate.amount,
                    "rate_unit": value.rate.unit,
                    "scaled_by_shape": value.scaled_by_shape,
                    "sort_order": value.sort_order,
                }
                for attribute in attributes
                for value in attribute.values
            ],
        )
        await connection.execute(
            insert(products_table),
            [{"id": product.id, "name": product.name, "slug": product.slug}],
        )
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": product.id,
                    "attribute_id": declared.attribute_id,
                    "value_id": declared.value_id,
                }
                for declared in product.declared_values
            ],
        )


async def prime_pricing_settings(engine: AsyncEngine) -> None:
    """Insert the single settings row with the owner's demo bounds."""
    settings = demo_settings()
    async with engine.begin() as connection:
        await connection.execute(
            insert(pricing_settings_table),
            [
                {
                    "id": settings.id,
                    "min_area": settings.min_area,
                    "min_order_total": settings.min_order_total,
                },
            ],
        )


async def corrupt_a_declaration_directly(engine: AsyncEngine) -> None:
    """Point the product's blade at a value of another attribute.

    The foreign keys allow it and no use case can produce it: this is what a
    defect in the data looks like, and the calculation must not price it.
    """
    async with engine.begin() as connection:
        await connection.execute(
            update(product_declared_values_table)
            .where(
                product_declared_values_table.c.product_id == PRODUCT,
                product_declared_values_table.c.attribute_id == BLADE,
            )
            .values(value_id=ALUMINIUM),
        )
