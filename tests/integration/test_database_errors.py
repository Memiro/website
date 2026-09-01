"""The SQLSTATE contract the HTTP error handlers classify database failures on."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.errors import UNIQUE_VIOLATION, sqlstate_of

_SHARED_SLUG = "duplicate-probe"


async def _insert_category_directly(engine: AsyncEngine, slug: str) -> None:
    """Write one category row past the domain, to provoke a database-level failure."""
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """INSERT INTO categories (id, name, slug, sort_order, created_at, updated_at)
                   VALUES (:id, 'Дубль', :slug, 0, now(), now())"""
            ),
            {"id": uuid.uuid4(), "slug": slug},
        )


async def test_a_duplicate_row_reports_the_sqlstate_the_error_handler_reads(engine: AsyncEngine) -> None:
    """Postgres reports a broken uniqueness as 23505, which is what turns the failure into 429."""
    await _insert_category_directly(engine, _SHARED_SLUG)

    with pytest.raises(IntegrityError) as failure:
        await _insert_category_directly(engine, _SHARED_SLUG)

    assert sqlstate_of(failure.value) == UNIQUE_VIOLATION
