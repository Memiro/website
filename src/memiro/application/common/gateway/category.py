from abc import abstractmethod
from typing import Protocol

from memiro.entities.common.identifiers import CategoryId


class CategoryGateway(Protocol):
    """Storage port of the catalogue sections.

    A section has no rules of its own and therefore no aggregate in the
    domain (ADR-0012 leaves its CRUD to the admin mirror); what the write
    path of the dictionary needs from storage is whether one exists.
    """

    @abstractmethod
    async def exists(self, category_id: CategoryId) -> bool:
        """Tell whether the catalogue holds a section under this identifier."""
        raise NotImplementedError
