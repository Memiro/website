from typing import Any

from dishka import STRICT_VALIDATION, AsyncContainer, make_async_container

from memiro.adapters.db.config import DbConfig
from memiro.adapters.smtp.config import EmailConfig
from memiro.application.submit_inquiry.config import LegalConfig
from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.di.providers.adapters import AdapterProvider
from memiro.bootstrap.di.providers.config import ConfigProvider
from memiro.bootstrap.di.providers.interactors import InteractorProvider
from memiro_common.observability.config import ObservabilityConfig


def _context(config: Config) -> dict[Any, Any]:
    return {
        DbConfig: config.db,
        EmailConfig: config.email,
        LegalConfig: config.legal,
        ObservabilityConfig: config.observability,
    }


def get_async_container(config: Config) -> AsyncContainer:
    """Assemble the DI container; the graph is validated at process start (§9.6)."""
    return make_async_container(
        ConfigProvider(),
        AdapterProvider(),
        InteractorProvider(),
        context=_context(config),
        validation_settings=STRICT_VALIDATION,
    )
