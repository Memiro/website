"""The drift test: the only test in the suite that knows both schemas.

Alembic owns the domain tables and Django only mirrors them, so nothing but a
test can notice that a migration moved a column the mirror still declares.
Compared: the set of tables, the columns, their nullability, their coarse type
and the unique constraints. Defaults are not compared — they live in the
domain, and the mirror never writes.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.apps import apps
from django.db import connections, models
from sqlalchemy import ARRAY, Connection, inspect
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.types import TypeEngine

# Service tables Django migrates for itself; the mirrors have nothing to say
# about them.
SERVICE_PREFIXES = ("auth_", "django_")
ALEMBIC_TABLE = "alembic_version"

pytestmark = pytest.mark.usefixtures("admin_site")

COARSE_TYPES = (
    ("uuid", "uuid"),
    ("varchar", "text"),
    ("character varying", "text"),
    ("text", "text"),
    ("integer", "integer"),
    ("bigint", "integer"),
    ("smallint", "integer"),
    ("numeric", "numeric"),
    ("bool", "boolean"),
    ("timestamp", "timestamp"),
    ("jsonb", "json"),
)


def _coarse(declared: str) -> str:
    """Reduce a Postgres type to the family the mirror has to agree on."""
    lowered = declared.lower()
    if lowered.endswith("[]"):
        return f"array of {_coarse(lowered.removesuffix('[]'))}"
    for prefix, family in COARSE_TYPES:
        if lowered.startswith(prefix):
            return family
    message = f"Unknown column type in the comparison: {declared}"
    raise AssertionError(message)


def _reflected_type(column_type: TypeEngine[Any]) -> str:
    """Spell a reflected type the way Django spells the same column."""
    if isinstance(column_type, ARRAY):
        return f"{column_type.item_type}[]"
    return str(column_type)


def _mirrors() -> Iterator[Any]:
    return iter(apps.get_app_config("memiro").get_models())


def _mirror_columns(mirror: Any) -> dict[str, tuple[str, bool]]:
    connection = connections["default"]
    return {
        field.column: (_coarse(str(field.db_type(connection))), field.null)
        for field in mirror._meta.concrete_fields  # noqa: SLF001  # ``_meta`` is Django's documented model API
        if not isinstance(field, models.CompositePrimaryKey)
    }


def _mirror_unique_constraints(mirror: Any) -> set[tuple[str, ...]]:
    meta = mirror._meta  # noqa: SLF001  # ``_meta`` is Django's documented model API
    single = {(field.column,) for field in meta.concrete_fields if field.unique and not field.primary_key}
    declared = {
        tuple(meta.get_field(name).column for name in constraint.fields)
        for constraint in meta.constraints
        if isinstance(constraint, models.UniqueConstraint)
    }
    return single | declared


def _mirror_primary_key(mirror: Any) -> tuple[str, ...]:
    meta = mirror._meta  # noqa: SLF001  # ``_meta`` is Django's documented model API
    if isinstance(meta.pk, models.CompositePrimaryKey):
        return tuple(meta.get_field(name).column for name in meta.pk.field_names)
    return (meta.pk.column,)


@pytest.fixture(scope="session")
async def schema(admin_database_url: str) -> dict[str, dict[str, Any]]:
    """Reflect the migrated database once: tables, columns, keys, unique constraints."""
    engine: AsyncEngine = create_async_engine(admin_database_url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_reflect)
    finally:
        await engine.dispose()


def _reflect(connection: Connection) -> dict[str, dict[str, Any]]:
    inspector = inspect(connection)
    names = [
        name for name in inspector.get_table_names() if name != ALEMBIC_TABLE and not name.startswith(SERVICE_PREFIXES)
    ]
    return {
        name: {
            "columns": {
                column["name"]: (_coarse(_reflected_type(column["type"])), column["nullable"])
                for column in inspector.get_columns(name)
            },
            "primary_key": tuple(inspector.get_pk_constraint(name)["constrained_columns"]),
            "unique": {tuple(constraint["column_names"]) for constraint in inspector.get_unique_constraints(name)},
        }
        for name in names
    }


async def test_every_domain_table_has_a_mirror_and_every_mirror_a_table(schema: dict[str, dict[str, Any]]) -> None:
    """A table alembic created and Django never learned about is drift too."""
    mirrored = {mirror._meta.db_table for mirror in _mirrors()}  # noqa: SLF001  # Django's documented model API

    assert mirrored == set(schema)


async def test_every_mirror_declares_the_columns_its_table_has(schema: dict[str, dict[str, Any]]) -> None:
    """Column names, coarse types and nullability, mirror by mirror."""
    declared = {mirror._meta.db_table: _mirror_columns(mirror) for mirror in _mirrors()}  # noqa: SLF001

    assert declared == {name: table["columns"] for name, table in schema.items()}


async def test_every_mirror_declares_the_primary_key_its_table_has(schema: dict[str, dict[str, Any]]) -> None:
    """A composite key the mirror spells as a single one makes the admin edit the wrong row."""
    declared = {mirror._meta.db_table: _mirror_primary_key(mirror) for mirror in _mirrors()}  # noqa: SLF001

    assert declared == {name: table["primary_key"] for name, table in schema.items()}


async def test_every_mirror_declares_the_unique_constraints_its_table_has(schema: dict[str, dict[str, Any]]) -> None:
    """Uniqueness the mirror does not know about is a form the admin lets the owner break."""
    declared = {mirror._meta.db_table: _mirror_unique_constraints(mirror) for mirror in _mirrors()}  # noqa: SLF001

    assert declared == {name: table["unique"] for name, table in schema.items()}


async def test_no_mirror_lets_django_migrate_or_delete_a_domain_row() -> None:
    """Alembic owns the tables and the database owns deletion — every mirror says so."""
    trespassing = [
        mirror._meta.db_table  # noqa: SLF001
        for mirror in _mirrors()
        if mirror._meta.managed  # noqa: SLF001
        or any(
            field.remote_field is None or field.remote_field.on_delete is not models.DO_NOTHING
            for field in mirror._meta.concrete_fields  # noqa: SLF001
            if isinstance(field, models.ForeignKey)
        )
    ]

    assert trespassing == []
