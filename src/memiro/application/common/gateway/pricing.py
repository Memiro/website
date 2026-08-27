from abc import abstractmethod
from typing import Protocol

from memiro.entities.pricing.pricing_settings import PricingSettings


class PricingSettingsGateway(Protocol):
    """Storage port of the ``PricingSettings`` aggregate."""

    @abstractmethod
    async def get(self) -> PricingSettings | None:
        """Load the single settings row of the site, or ``None`` if it was never created."""
        raise NotImplementedError
