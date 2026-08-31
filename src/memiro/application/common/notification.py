from abc import abstractmethod
from typing import Protocol

from memiro.entities.common.identifiers import InquiryId


class InquiryNotificationBus(Protocol):
    """Publish a saved inquiry to manager channels without surfacing delivery failures.

    Implementations load only the aggregate's persisted snapshot by identifier,
    attempt every configured external channel, and absorb delivery failures.
    """

    @abstractmethod
    async def notify(self, inquiry_id: InquiryId) -> None:
        """Deliver the saved aggregate's immutable snapshots after its commit."""
        raise NotImplementedError
