from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class DbConfig:
    """Connection settings for the Postgres database."""

    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def url(self) -> str:
        """Build the SQLAlchemy URL for the asyncpg driver."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
