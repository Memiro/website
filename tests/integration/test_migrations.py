import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from memiro.adapters.db.config import DbConfig
from memiro.adapters.db.migrations import create_migration_config

_PREVIOUS_REVISION = "9f1c0a3b7d21"


@dataclass(frozen=True, slots=True)
class _SeededDatabase:
    url: str
    attribute_id: uuid.UUID
    value_id: uuid.UUID
    product_id: uuid.UUID


def _upgrade(db_url: str, revision: str) -> None:
    command.upgrade(create_migration_config(db_url), revision)


def _downgrade(db_url: str, revision: str) -> None:
    command.downgrade(create_migration_config(db_url), revision)


@pytest.fixture
async def database_at_previous_revision(
    postgres: PostgresContainer,
    admin_engine: AsyncEngine,
) -> AsyncIterator[_SeededDatabase]:
    """Create and seed an isolated database at the migration's previous revision."""
    database_name = f"migration_{uuid.uuid4().hex}"
    db_config = DbConfig(
        host=postgres.get_container_host_ip(),
        port=int(postgres.get_exposed_port(5432)),
        user=postgres.username,
        password=postgres.password,
        database=database_name,
    )
    async with admin_engine.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    await asyncio.to_thread(_upgrade, db_config.url, _PREVIOUS_REVISION)

    attribute_id = uuid.uuid4()
    value_id = uuid.uuid4()
    product_id = uuid.uuid4()
    settings_id = uuid.uuid4()
    engine = create_async_engine(db_config.url)
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO attributes (id, name, sort_order) VALUES (:id, 'Blade', 1)"),
            {"id": attribute_id},
        )
        await connection.execute(
            text(
                """INSERT INTO attribute_values
                   (id, attribute_id, name, rate_amount, rate_unit, scaled_by_shape, sort_order)
                   VALUES (:id, :attribute_id, 'Silver', 4500, 'SQUARE_METER', true, 1)"""
            ),
            {"id": value_id, "attribute_id": attribute_id},
        )
        await connection.execute(
            text("INSERT INTO products (id, name, slug) VALUES (:id, 'Mirror', 'mirror')"),
            {"id": product_id},
        )
        await connection.execute(
            text(
                """INSERT INTO product_declared_values (product_id, attribute_id, value_id)
                   VALUES (:product_id, :attribute_id, :value_id)"""
            ),
            {"product_id": product_id, "attribute_id": attribute_id, "value_id": value_id},
        )
        await connection.execute(
            text(
                """INSERT INTO pricing_settings (id, min_area, min_order_total)
                   VALUES (:id, 0.25, 2000)"""
            ),
            {"id": settings_id},
        )
    await engine.dispose()

    yield _SeededDatabase(
        url=db_config.url,
        attribute_id=attribute_id,
        value_id=value_id,
        product_id=product_id,
    )

    async with admin_engine.connect() as connection:
        await connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))


async def test_pricing_migrations_preserve_existing_rows(
    database_at_previous_revision: _SeededDatabase,
) -> None:
    """Existing pricing rows receive compatible gates and no permanent server defaults."""
    seeded = database_at_previous_revision

    await asyncio.to_thread(_upgrade, seeded.url, "head")

    engine = create_async_engine(seeded.url)
    async with engine.connect() as connection:
        attribute = (
            await connection.execute(
                text(
                    """SELECT category_id, kind, parent_ids, is_customer_changeable
                       FROM attributes WHERE id = :id"""
                ),
                {"id": seeded.attribute_id},
            )
        ).one()
        value = (
            await connection.execute(
                text(
                    """SELECT scaled_by_size_surcharge
                       FROM attribute_values WHERE id = :id"""
                ),
                {"id": seeded.value_id},
            )
        ).one()
        product = (
            await connection.execute(
                text(
                    """SELECT category_id, is_published, hides_calculated_price, price_from
                       FROM products WHERE id = :id"""
                ),
                {"id": seeded.product_id},
            )
        ).one()
        declaration = (
            await connection.execute(
                text(
                    """SELECT value_id, quantity FROM product_declared_values
                       WHERE product_id = :product_id AND attribute_id = :attribute_id"""
                ),
                {"product_id": seeded.product_id, "attribute_id": seeded.attribute_id},
            )
        ).one()
        temporary_defaults = (
            await connection.execute(
                text(
                    """SELECT count(*) FROM information_schema.columns
                       WHERE table_schema = 'public'
                         AND column_name IN (
                           'category_id', 'kind', 'parent_ids', 'is_customer_changeable',
                           'marks_absence', 'is_published', 'hides_calculated_price',
                           'max_long_side_mm', 'max_short_side_mm',
                           'scaled_by_size_surcharge'
                         )
                         AND column_default IS NOT NULL"""
                )
            )
        ).scalar_one()
        variant_table = (await connection.execute(text("SELECT to_regclass('public.product_variants')"))).scalar_one()
        variant_constraints = set(
            (
                await connection.execute(
                    text(
                        """SELECT constraint_name FROM information_schema.table_constraints
                           WHERE table_schema = 'public'
                             AND table_name = 'product_variants'"""
                    )
                )
            ).scalars()
        )
    await engine.dispose()

    assert attribute == (product.category_id, "SELECT", [], True)
    assert value == (False,)
    assert product.is_published
    assert not product.hides_calculated_price
    assert product.price_from is None
    assert declaration == (seeded.value_id, None)
    assert temporary_defaults == 0
    assert variant_table == "product_variants"
    assert "ck_product_variants_sort_order_non_negative" in variant_constraints
    assert "uq_product_variants_product_fingerprint" in variant_constraints


async def test_pricing_gate_downgrade_refuses_unrepresentable_declarations(
    database_at_previous_revision: _SeededDatabase,
) -> None:
    """Downgrade refuses declarations the previous non-null schema cannot represent."""
    seeded = database_at_previous_revision
    await asyncio.to_thread(_upgrade, seeded.url, "head")
    engine = create_async_engine(seeded.url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """UPDATE product_declared_values SET value_id = NULL, quantity = 2.5
                   WHERE product_id = :product_id AND attribute_id = :attribute_id"""
            ),
            {"product_id": seeded.product_id, "attribute_id": seeded.attribute_id},
        )
    await engine.dispose()

    with pytest.raises(RuntimeError, match="Cannot downgrade pricing gates"):
        await asyncio.to_thread(_downgrade, seeded.url, _PREVIOUS_REVISION)


async def test_migrations_leave_every_product_in_a_category_that_exists(
    database_at_previous_revision: _SeededDatabase,
) -> None:
    """The category the backfill stamps on legacy products is a row, not a dangling identifier."""
    seeded = database_at_previous_revision

    await asyncio.to_thread(_upgrade, seeded.url, "head")

    engine = create_async_engine(seeded.url)
    async with engine.connect() as connection:
        orphans = (
            await connection.execute(
                text(
                    """SELECT count(*) FROM products
                       WHERE category_id NOT IN (SELECT id FROM categories)"""
                )
            )
        ).scalar_one()
    await engine.dispose()

    assert orphans == 0


async def test_migrations_keep_a_shape_factor_that_is_not_whole_kopecks(
    database_at_previous_revision: _SeededDatabase,
) -> None:
    """A FACTOR rate is a multiplier, not money: 1.125 must survive as 1.125, not round to 1.13."""
    seeded = database_at_previous_revision
    await asyncio.to_thread(_upgrade, seeded.url, "head")
    factor_id = uuid.uuid4()

    engine = create_async_engine(seeded.url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """INSERT INTO attribute_values
                   (id, attribute_id, name, rate_amount, rate_unit, scaled_by_shape, sort_order,
                    marks_absence, scaled_by_size_surcharge)
                   VALUES (:id, :attribute_id, 'Round', 1.125, 'FACTOR', false, 2, false, false)"""
            ),
            {"id": factor_id, "attribute_id": seeded.attribute_id},
        )
    async with engine.connect() as connection:
        stored = (
            await connection.execute(
                text("SELECT rate_amount FROM attribute_values WHERE id = :id"),
                {"id": factor_id},
            )
        ).scalar_one()
    await engine.dispose()

    assert stored == Decimal("1.125")
