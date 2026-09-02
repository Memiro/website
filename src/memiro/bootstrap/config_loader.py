import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from memiro.adapters.db.config import DbConfig
from memiro.adapters.smtp.config import EmailConfig
from memiro.application.submit_inquiry import LegalConfig
from memiro.presentation.django_admin.config import AdminConfig
from memiro_common.observability.config import ObservabilityConfig

# The only environment variable the application configuration reads; the
# admin's own credentials are a deployment secret and stay out of git
# (``ensure_superuser``).
CONFIG_PATH_ENV = "APP_CONFIG_PATH"


@dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    """Root of the application configuration; sections are fields (§11.2)."""

    db: DbConfig
    observability: ObservabilityConfig
    legal: LegalConfig
    email: EmailConfig = field(default_factory=EmailConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)

    @classmethod
    def load(cls) -> Self:
        """Read the TOML file pointed to by ``APP_CONFIG_PATH``."""
        path = Path(os.environ[CONFIG_PATH_ENV])
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls(
            db=DbConfig(**data["db"]),
            observability=ObservabilityConfig(**data["observability"]),
            email=EmailConfig(**data.get("email", {})),
            legal=LegalConfig(**data["legal"]),
            admin=AdminConfig.from_section(data.get("admin", {})),
        )
