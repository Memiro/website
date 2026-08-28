from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig

_SCRIPT_LOCATION = Path(__file__).parent / "alembic"


def create_migration_config(db_url: str) -> AlembicConfig:
    """Build an Alembic config for the database at ``db_url``."""
    config = AlembicConfig()
    config.set_main_option("script_location", str(_SCRIPT_LOCATION))
    config.attributes["db_url"] = db_url
    return config


def apply_migrations(db_url: str) -> None:
    """Upgrade the database at ``db_url`` to the alembic head.

    The URL travels through ``config.attributes`` — the same key the tests
    use to point migrations at a template database (§8.5).
    """
    command.upgrade(create_migration_config(db_url), "head")
