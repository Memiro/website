from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class DbConfig:
    """Connection settings for the Postgres database."""

    host: str
    port: int
    user: str
    password: str
    database: str
    # Without a wait limit a queued lock hangs the request forever; the
    # bounded wait is what makes "retry" (429) an honest answer to a race.
    lock_timeout_ms: int = 3000

    @property
    def server_settings(self) -> dict[str, str]:
        """Session settings asyncpg applies to every connection it opens."""
        return {"lock_timeout": f"{self.lock_timeout_ms}ms"}

    @property
    def url(self) -> str:
        """Build the SQLAlchemy URL for the asyncpg driver."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
