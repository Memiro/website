from dataclasses import dataclass
from enum import StrEnum

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
    password: str = ""
    from_address: str = "memiro.ru@yandex.ru"
    manager_address: str = ""
    timeout_seconds: float = 10.0

    @property
    def encryption(self) -> SMTPEncryption:
        """Derive the Yandex SMTP encryption mode from its configured port."""
        if self.port == SMTP_SSL_PORT:
            return SMTPEncryption.SSL
        if self.port == SMTP_STARTTLS_PORT:
            return SMTPEncryption.STARTTLS
        return SMTPEncryption.NONE
