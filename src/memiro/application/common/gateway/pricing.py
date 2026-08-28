from abc import abstractmethod
from typing import Protocol

from memiro.entities.pricing.pricing_settings import PricingSettings


class PricingSettingsGateway(Protocol):
    """Storage port of the ``PricingSettings`` aggregate."""

    @abstractmethod
    async def get_with_surcharges(self) -> PricingSettings | None:
        """Load the single settings aggregate with its surcharge tiers, or ``None`` if absent."""
        raise NotImplementedError
