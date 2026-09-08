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
from memiro.adapters.db.gateways.attribute import SAAttributeGateway
from memiro.adapters.db.gateways.catalog_read import SACatalogReadGateway
from memiro.adapters.db.gateways.category import SACategoryGateway
from memiro.adapters.db.gateways.inquiry import SAInquiryGateway
from memiro.adapters.db.gateways.landing import SALandingGateway
from memiro.adapters.db.gateways.pricing import SAPricingSettingsGateway
from memiro.adapters.db.gateways.product import SAProductGateway
from memiro.adapters.db.gateways.site import SASiteGateway
from memiro.adapters.db.gateways.work import SAWorkGateway
from memiro.adapters.events.in_process import InProcessEventBus
from memiro.adapters.smtp.inquiry_notification import SMTPInquiryNotificationBus, Transport, smtp_transport
from memiro.adapters.storage.local_product_image import LocalProductImageStorage
from memiro.adapters.storage.local_work_photo import LocalWorkPhotoStorage
from memiro.application.common.dispatch_log import DispatchLog
from memiro_common.clock import SystemClock
from memiro_common.uow import UoW


class AdapterProvider(Provider):
    """Port implementations and the resources they live on."""

    clock = provide(WithParents[SystemClock], scope=Scope.APP)

    product_gateway = provide(WithParents[SAProductGateway], scope=Scope.REQUEST)
    attribute_gateway = provide(WithParents[SAAttributeGateway], scope=Scope.REQUEST)
    catalog_read_gateway = provide(WithParents[SACatalogReadGateway], scope=Scope.REQUEST)
    category_gateway = provide(WithParents[SACategoryGateway], scope=Scope.REQUEST)
    inquiry_gateway = provide(WithParents[SAInquiryGateway], scope=Scope.REQUEST)
    landing_gateway = provide(WithParents[SALandingGateway], scope=Scope.REQUEST)
    pricing_settings_gateway = provide(WithParents[SAPricingSettingsGateway], scope=Scope.REQUEST)
    site_gateway = provide(WithParents[SASiteGateway], scope=Scope.REQUEST)
    work_gateway = provide(WithParents[SAWorkGateway], scope=Scope.REQUEST)
    inquiry_notification_bus = provide(WithParents[SMTPInquiryNotificationBus], scope=Scope.REQUEST)
    event_bus = provide(WithParents[InProcessEventBus], scope=Scope.REQUEST)
    product_image_storage = provide(WithParents[LocalProductImageStorage], scope=Scope.APP)
    work_photo_storage = provide(WithParents[LocalWorkPhotoStorage], scope=Scope.APP)

    @provide(scope=Scope.REQUEST)
    def get_dispatch_log(self) -> DispatchLog:
        """Provide the empty tally the after-commit subscribers of this request fill in."""
        return DispatchLog()

    @provide(scope=Scope.APP)
    def get_email_transport(self) -> Transport:
        """Hand the bus the blocking SMTP send it runs off the event loop."""
        return smtp_transport

    @provide(scope=Scope.APP)
    async def get_engine(self, config: DbConfig) -> AsyncIterator[AsyncEngine]:
        """Provide the process-wide engine, disposed on container close."""
        engine = create_async_engine(config.url, connect_args={"server_settings": config.server_settings})
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
