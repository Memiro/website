"""The bus of one process: an event published after a commit is handled in the request that published it.

There is no queue and no worker in this contour (decision 6): the owner saves
a tariff and leaves the screen with the recalculated prices already stored. A
subscriber that fails is a warning — the transaction it followed has ended,
and there is nothing left to roll back (ADR-0014).
"""

from typing import override

import structlog

from memiro.application.common.dispatch_log import DispatchLog
from memiro.application.common.event import DomainEvent, EventBus
from memiro.application.reprice_products import RepriceProducts
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class InProcessEventBus(EventBus):
    """Runs the subscribers of an event synchronously, in the request that published it."""

    def __init__(self, reprice_products: RepriceProducts, dispatch_log: DispatchLog) -> None:
        """Keep the subscribers of this process and the log the screen reads back."""
        self._reprice_products = reprice_products
        self._dispatch_log = dispatch_log

    @override
    async def publish(self, event: DomainEvent) -> None:
        """Reprice the catalogue behind both events the context publishes so far."""
        logger.debug("Publishing a domain event", domain_event=type(event).__name__)
        try:
            self._dispatch_log.record((await self._reprice_products.execute()).product_count)
        except Exception as failure:  # a subscriber never fails the change it followed
            self._dispatch_log.record_failure()
            logger.warning(
                "A subscriber failed after the change it followed was committed",
                domain_event=type(event).__name__,
                error=type(failure).__name__,
                exc_info=True,
            )
