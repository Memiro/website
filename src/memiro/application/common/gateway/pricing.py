from abc import abstractmethod
from typing import Protocol

from memiro.entities.pricing.pricing_settings import PricingSettings


class PricingSettingsGateway(Protocol):
    """Storage port of the ``PricingSettings`` aggregate."""

    @abstractmethod
    async def get_with_surcharges(self, *, for_update: bool = False) -> PricingSettings | None:
        """Load the single settings aggregate with its surcharge tiers, or ``None`` if absent.

        Implementations must load the tiers eagerly — the owner's command
        replaces the set whole — and ``for_update`` locks the aggregate root
        until the current transaction ends, raising ``LockTimeoutError`` when
        the lock is refused.
        """
        raise NotImplementedError
