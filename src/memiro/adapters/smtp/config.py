from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

SMTP_SSL_PORT = 465
SMTP_STARTTLS_PORT = 587


class SMTPEncryption(StrEnum):
    """Transport encryption modes supported by the SMTP adapter."""

    NONE = "none"
    STARTTLS = "starttls"
    SSL = "ssl"


@dataclass(frozen=True, slots=True, kw_only=True)
class EmailConfig:
    """Configuration of the optional manager email channel."""

    enabled: bool = False
    host: str = "smtp.yandex.ru"
    port: int = SMTP_SSL_PORT
    username: str = "memiro.ru@yandex.ru"
    # The secret itself never sits in the TOML: the loader fills ``password``
    # from the file ``password_file`` names, relative to the config's directory.
    password: str = ""
    password_file: str = ""
    from_address: str = "memiro.ru@yandex.ru"
    manager_address: str = ""
    timeout_seconds: float = 10.0

    @classmethod
    def from_section(cls, section: dict[str, Any], config_dir: Path) -> Self:
        """Build the section from TOML, reading the password from its file; a missing file leaves it empty."""
        config = cls(**section)
        if not config.password_file:
            return config
        password_path = config_dir / config.password_file
        if not password_path.exists():
            return config
        return replace(config, password=password_path.read_text(encoding="utf-8").strip())

    @property
    def encryption(self) -> SMTPEncryption:
        """Derive the Yandex SMTP encryption mode from its configured port."""
        if self.port == SMTP_SSL_PORT:
            return SMTPEncryption.SSL
        if self.port == SMTP_STARTTLS_PORT:
            return SMTPEncryption.STARTTLS
        return SMTPEncryption.NONE
