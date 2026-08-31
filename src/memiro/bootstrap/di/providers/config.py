from dishka import Provider, Scope, from_context

from memiro.adapters.db.config import DbConfig
from memiro.adapters.smtp.config import EmailConfig
from memiro_common.observability.config import ObservabilityConfig


class ConfigProvider(Provider):
    """Config sections arrive via container context — nothing reads TOML here (§9.2)."""

    scope = Scope.APP

    db = from_context(DbConfig)
    email = from_context(EmailConfig)
    observability = from_context(ObservabilityConfig)
