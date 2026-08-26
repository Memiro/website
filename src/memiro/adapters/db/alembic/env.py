import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import SchemaItem

from memiro.adapters.db.registry import mapper_registry

target_metadata = mapper_registry.metadata


def _include_object(
    _object: SchemaItem,
    _name: str | None,
    type_: str,
    reflected: bool,  # noqa: FBT001  # the signature is alembic's contract
    compare_to: SchemaItem | None,
) -> bool:
    """Keep alembic blind to tables it does not own (``auth_*``, ``django_*``)."""
    return not (type_ == "table" and reflected and compare_to is None)


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    # The URL is always injected by the caller (CLI or tests) — env.py never
    # reads an ini file or the environment itself.
    engine = create_async_engine(context.config.attributes["db_url"])
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    msg = "Offline migrations are not supported; the URL is injected at runtime."
    raise RuntimeError(msg)

asyncio.run(_run_async_migrations())
