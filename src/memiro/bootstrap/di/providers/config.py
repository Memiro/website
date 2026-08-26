from dishka import Provider, Scope, from_context

from memiro.adapters.db.config import DbConfig
from memiro.bootstrap.config_loader import ObservabilityConfig


class ConfigProvider(Provider):
    """Config sections arrive via container context — nothing reads TOML here (§9.2)."""

    scope = Scope.APP

    db = from_context(DbConfig)
    observability = from_context(ObservabilityConfig)
