"""What a committed change tells the rest of the context, and the port that carries it (ADR-0014).

One transaction is one aggregate: an event is published strictly after the
commit of the change that raised it, and carries identifiers only — a
subscriber reads the state it needs for itself, in its own transaction.
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from memiro.entities.common.identifiers import AttributeId, PricingSettingsId


@dataclass(frozen=True, slots=True)
class TariffChanged:
    """The dictionary of one attribute was restated, tariffs included."""

    attribute_id: AttributeId


@dataclass(frozen=True, slots=True)
class PricingSettingsChanged:
    """The bounds of calculation or the surcharge table were restated."""

    pricing_settings_id: PricingSettingsId


type DomainEvent = TariffChanged | PricingSettingsChanged


@dataclass(slots=True)
class DispatchLog:
    """What the after-commit subscribers of this request did, for the screen that started it."""

    repriced_products: int = 0
    failed: bool = False

    def record(self, repriced_products: int) -> None:
        """Add what one subscriber repriced."""
        self.repriced_products += repriced_products

    def record_failure(self) -> None:
        """Remember that a subscriber did not finish."""
        self.failed = True

    def merge(self, other: "DispatchLog") -> None:
        """Add what the subscribers of one more command did."""
        self.repriced_products += other.repriced_products
        self.failed = self.failed or other.failed


class EventBus(Protocol):
    """Port carrying a committed change to the subscribers of the context."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Hand one event to its subscribers.

        Implementations never raise: the change is already committed, and a
        subscriber that fails leaves a warning in the log and a note in the
        dispatch log, not a rollback.
        """
        raise NotImplementedError
