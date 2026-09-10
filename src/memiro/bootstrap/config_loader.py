import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Self

from memiro.adapters.db.config import DbConfig
from memiro.adapters.smtp.config import EmailConfig
from memiro.adapters.storage.config import MediaConfig
from memiro.application.submit_inquiry import LegalConfig
from memiro.presentation.django_admin.config import AdminConfig
from memiro_common.observability.config import ObservabilityConfig

# The only environment variable the application configuration reads; the
# admin's own credentials are a deployment secret and stay out of git
# (``ensure_superuser``).
CONFIG_PATH_ENV = "APP_CONFIG_PATH"


def _email_section(section: dict[str, Any], config_dir: Path) -> EmailConfig:
    """Build the email section, reading the password from the file it names; a missing file leaves it empty."""
    config = EmailConfig(**section)
    if not config.password_file:
        return config
    password_path = config_dir / config.password_file
    if not password_path.exists():
        return config
    return replace(config, password=password_path.read_text(encoding="utf-8").strip())


@dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    """Root of the application configuration; sections are fields (§11.2)."""

    db: DbConfig
    observability: ObservabilityConfig
    legal: LegalConfig
    media: MediaConfig
    email: EmailConfig = field(default_factory=EmailConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)

    @classmethod
    def load(cls) -> Self:
        """Read the TOML file pointed to by ``APP_CONFIG_PATH``."""
        return cls.from_file(Path(os.environ[CONFIG_PATH_ENV]))

    @classmethod
    def from_file(cls, path: Path) -> Self:
        """Read one TOML file; the secrets its sections name by file are looked up next to it."""
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls(
            db=DbConfig(**data["db"]),
            observability=ObservabilityConfig(**data["observability"]),
            email=_email_section(data.get("email", {}), path.parent),
            legal=LegalConfig(**data["legal"]),
            media=MediaConfig(root=Path(data["media"]["root"])),
            admin=AdminConfig.from_section(data.get("admin", {})),
        )
