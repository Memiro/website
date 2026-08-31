from abc import abstractmethod
from typing import Protocol

from memiro.entities.common.identifiers import InquiryId
from memiro.entities.inquiry.entity import Inquiry


class InquiryGateway(Protocol):
    """Storage port of the ``Inquiry`` aggregate."""

    @abstractmethod
    async def get(self, inquiry_id: InquiryId) -> Inquiry | None:
        """Load an inquiry with every private item snapshot, or ``None`` if it does not exist."""
        raise NotImplementedError
