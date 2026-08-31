from collections.abc import AsyncIterator

from dishka import (
    AnyOf,
    Provider,
    Scope,
    WithParents,
    # dishka's `provide` overloads carry partially unknown generics — a library trait.
    provide,  # pyright: ignore[reportUnknownVariableType]
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from memiro.adapters.db.config import DbConfig
from memiro.adapters.db.gateways.catalog import SAAttributeGateway, SAProductGateway
from memiro.adapters.db.gateways.catalog_read import SACatalogReadGateway
from memiro.adapters.db.gateways.inquiry import SAInquiryGateway
from memiro.adapters.db.gateways.pricing import SAPricingSettingsGateway
from memiro.adapters.smtp.composite import CompositeInquiryNotificationBus
from memiro.adapters.smtp.config import EmailConfig
from memiro.adapters.smtp.inquiry_notification import SMTPInquiryNotificationBus
from memiro.application.common.notification import InquiryNotificationBus
from memiro_common.clock import SystemClock
from memiro_common.uow import UoW


class AdapterProvider(Provider):
    """Port implementations and the resources they live on."""

    clock = provide(WithParents[SystemClock], scope=Scope.APP)

    product_gateway = provide(WithParents[SAProductGateway], scope=Scope.REQUEST)
    attribute_gateway = provide(WithParents[SAAttributeGateway], scope=Scope.REQUEST)
    catalog_read_gateway = provide(WithParents[SACatalogReadGateway], scope=Scope.REQUEST)
    inquiry_gateway = provide(WithParents[SAInquiryGateway], scope=Scope.REQUEST)
    pricing_settings_gateway = provide(WithParents[SAPricingSettingsGateway], scope=Scope.REQUEST)
    smtp_inquiry_notification_bus = provide(SMTPInquiryNotificationBus, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST, provides=InquiryNotificationBus)
    def get_inquiry_notification_bus(
        self,
        smtp_inquiry_notification_bus: SMTPInquiryNotificationBus,
        email: EmailConfig,
    ) -> CompositeInquiryNotificationBus:
        """Compose only the manager channels enabled by configuration."""
        channels: tuple[InquiryNotificationBus, ...] = (smtp_inquiry_notification_bus,) if email.enabled else ()
        return CompositeInquiryNotificationBus(channels)

    @provide(scope=Scope.APP)
    async def get_engine(self, config: DbConfig) -> AsyncIterator[AsyncEngine]:
        """Provide the process-wide engine, disposed on container close."""
        engine = create_async_engine(config.url)
        try:
            yield engine
        finally:
            await engine.dispose()

    @provide(scope=Scope.APP)
    def get_sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        """Provide the session factory bound to the engine."""
        # expire_on_commit=False: interactors read entity attributes after commit.
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def get_session(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AnyOf[AsyncSession, UoW]]:
        """Provide the request-scoped session doubling as the UoW port (§9.5)."""
        async with sessionmaker() as session:
            yield session
