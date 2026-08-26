import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from memiro.adapters.db.config import DbConfig
from memiro_common.observability.config import ObservabilityConfig

# The only environment variable the application reads.
CONFIG_PATH_ENV = "APP_CONFIG_PATH"


@dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    """Root of the application configuration; sections are fields (§11.2)."""

    db: DbConfig
    observability: ObservabilityConfig

    @classmethod
    def load(cls) -> Self:
        """Read the TOML file pointed to by ``APP_CONFIG_PATH``."""
        path = Path(os.environ[CONFIG_PATH_ENV])
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls(
            db=DbConfig(**data["db"]),
            observability=ObservabilityConfig(**data["observability"]),
        )
