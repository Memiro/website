"""Direct writes that stand in for the admin write path (§14.5.5).

There is no use case that creates a product, an attribute or the pricing
settings yet — the admin brings them with its own slice — so the arrangement
of a pricing test goes straight to the tables through named helpers.
"""

from decimal import Decimal

from sqlalchemy import delete, insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.tables import (
    attribute_values_table,
    attributes_table,
    pricing_settings_table,
    product_declared_values_table,
    products_table,
)
from memiro.entities.common.measure import Millimeters
from memiro.entities.common.money import Money
from tests.common.factory.catalog import (
    ALUMINIUM,
    BACKLIGHT,
    BLADE,
    CONTOUR,
    HEATING,
    NO_HEATING,
    PRODUCT,
    SILVER,
    WITH_HEATING,
    WITH_MOUNT,
    demo_attributes,
    demo_cutouts,
    demo_numeric_product,
    demo_product,
    demo_settings,
)


async def prime_dictionary(engine: AsyncEngine) -> None:
    """Insert the demo dictionary and the canonical product it describes."""
    attributes = demo_attributes()
    product = demo_product()
    async with engine.begin() as connection:
        await connection.execute(
            insert(attributes_table),
            [
                {
                    "id": attribute.id,
                    "category_id": attribute.category_id,
                    "name": attribute.name,
                    "kind": attribute.kind,
                    "parent_ids": attribute.parent_ids,
                    "is_customer_changeable": attribute.is_customer_changeable,
                    "sort_order": attribute.sort_order,
                }
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
                    "marks_absence": value.marks_absence,
                    "sort_order": value.sort_order,
                }
                for attribute in attributes
                for value in attribute.values
            ],
        )
        await connection.execute(
            insert(products_table),
            [
                {
                    "id": product.id,
                    "category_id": product.category_id,
                    "name": product.name,
                    "slug": product.slug,
                    "is_published": product.is_published,
                    "hides_calculated_price": product.hides_calculated_price,
                },
            ],
        )
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": product.id,
                    "attribute_id": declared.attribute_id,
                    "value_id": declared.configured.value_id,
                    "quantity": declared.configured.quantity,
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
                    "max_long_side_mm": settings.max_long_side_mm,
                    "max_short_side_mm": settings.max_short_side_mm,
                },
            ],
        )


async def prime_product_publication(engine: AsyncEngine, *, is_published: bool) -> None:
    """Set whether the canonical product is published."""
    async with engine.begin() as connection:
        await connection.execute(
            update(products_table).where(products_table.c.id == PRODUCT).values(is_published=is_published),
        )


async def prime_hidden_calculated_price(engine: AsyncEngine) -> None:
    """Hide the canonical product's calculated price from customers."""
    async with engine.begin() as connection:
        await connection.execute(
            update(products_table).where(products_table.c.id == PRODUCT).values(hides_calculated_price=True),
        )


async def prime_production_limits(
    engine: AsyncEngine,
    *,
    max_long_side_mm: Millimeters,
    max_short_side_mm: Millimeters,
) -> None:
    """Set the production limits of the single pricing-settings row."""
    settings = demo_settings()
    async with engine.begin() as connection:
        await connection.execute(
            update(pricing_settings_table)
            .where(pricing_settings_table.c.id == settings.id)
            .values(
                max_long_side_mm=max_long_side_mm,
                max_short_side_mm=max_short_side_mm,
            ),
        )


async def prime_incomplete_declaration(engine: AsyncEngine) -> None:
    """Leave the canonical product's blade declaration unfinished."""
    async with engine.begin() as connection:
        await connection.execute(
            update(product_declared_values_table)
            .where(
                product_declared_values_table.c.product_id == PRODUCT,
                product_declared_values_table.c.attribute_id == BLADE,
            )
            .values(value_id=None, quantity=None),
        )


async def prime_present_dependency(engine: AsyncEngine) -> None:
    """Make backlight present while leaving its dependent heating declaration absent."""
    async with engine.begin() as connection:
        await connection.execute(
            update(product_declared_values_table)
            .where(
                product_declared_values_table.c.product_id == PRODUCT,
                product_declared_values_table.c.attribute_id == BACKLIGHT,
            )
            .values(value_id=CONTOUR),
        )


async def prime_complete_heating_declaration(engine: AsyncEngine) -> None:
    """Declare explicit absence for heating so a customer may turn backlight on."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": PRODUCT,
                    "attribute_id": HEATING,
                    "value_id": NO_HEATING,
                    "quantity": None,
                },
            ],
        )


async def prime_paid_heating_declaration(engine: AsyncEngine) -> None:
    """Make backlight and its paid dependent heating present in the product."""
    async with engine.begin() as connection:
        await connection.execute(
            update(product_declared_values_table)
            .where(
                product_declared_values_table.c.product_id == PRODUCT,
                product_declared_values_table.c.attribute_id == BACKLIGHT,
            )
            .values(value_id=CONTOUR),
        )
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": PRODUCT,
                    "attribute_id": HEATING,
                    "value_id": WITH_HEATING,
                    "quantity": None,
                },
            ],
        )


async def prime_product_without_paid_values(engine: AsyncEngine) -> None:
    """Make every money-bearing declaration of the canonical product free."""
    async with engine.begin() as connection:
        await connection.execute(
            update(attribute_values_table)
            .where(attribute_values_table.c.id.in_([SILVER, ALUMINIUM, WITH_MOUNT]))
            .values(rate_amount=Money(amount=Decimal(0))),
        )


async def prime_non_changeable_attribute(engine: AsyncEngine) -> None:
    """Prevent customers from changing the canonical product's blade."""
    async with engine.begin() as connection:
        await connection.execute(
            update(attributes_table).where(attributes_table.c.id == BLADE).values(is_customer_changeable=False),
        )


async def prime_numeric_catalog(engine: AsyncEngine) -> None:
    """Replace the demo dictionary and product with one fractional numeric attribute."""
    attribute = demo_cutouts()
    product = demo_numeric_product(quantity=Decimal(1))
    settings = demo_settings()
    value = attribute.values[0]
    async with engine.begin() as connection:
        await connection.execute(delete(product_declared_values_table))
        await connection.execute(delete(attribute_values_table))
        await connection.execute(delete(attributes_table))
        await connection.execute(
            insert(attributes_table),
            [
                {
                    "id": attribute.id,
                    "category_id": attribute.category_id,
                    "name": attribute.name,
                    "kind": attribute.kind,
                    "parent_ids": attribute.parent_ids,
                    "is_customer_changeable": attribute.is_customer_changeable,
                    "sort_order": attribute.sort_order,
                },
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
                    "marks_absence": value.marks_absence,
                    "sort_order": value.sort_order,
                },
            ],
        )
        await connection.execute(
            update(products_table)
            .where(products_table.c.id == product.id)
            .values(
                category_id=product.category_id,
                name=product.name,
                slug=product.slug,
                is_published=product.is_published,
                hides_calculated_price=product.hides_calculated_price,
            ),
        )
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": product.id,
                    "attribute_id": product.declared_values[0].attribute_id,
                    "value_id": product.declared_values[0].configured.value_id,
                    "quantity": product.declared_values[0].configured.quantity,
                },
            ],
        )
        await connection.execute(
            update(pricing_settings_table)
            .where(pricing_settings_table.c.id == settings.id)
            .values(min_order_total=Money(amount=Decimal(0))),
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
