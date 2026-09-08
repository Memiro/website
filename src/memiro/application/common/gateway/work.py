from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from memiro.application.common.gateway.product_image import ImageUpload
from memiro.entities.common.identifiers import ProductId, WorkId


@dataclass(frozen=True, slots=True)
class WorkRow:
    """One work of the gallery as it is stored: a photograph, a caption and the mirror it shows."""

    id: WorkId
    photo_key: str
    product_id: ProductId | None
    title: str
    description: str
    is_published: bool
    sort_order: int


class WorkGateway(Protocol):
    """Storage port of the works the gallery is built from.

    A work carries no rules and therefore no aggregate in the domain
    (decision 49); what its commands need from storage is the row itself.
    """

    @abstractmethod
    async def get(self, work_id: WorkId) -> WorkRow | None:
        """Read one work, or ``None`` if the gallery holds no such work."""
        raise NotImplementedError

    @abstractmethod
    async def add(self, work: WorkRow) -> None:
        """Enter one work into the gallery within the current transaction."""
        raise NotImplementedError

    @abstractmethod
    async def replace(self, work: WorkRow) -> None:
        """Restate one work whole: the card is saved as one row, not field by field."""
        raise NotImplementedError

    @abstractmethod
    async def remove(self, work_id: WorkId) -> None:
        """Take one work out of the gallery within the current transaction."""
        raise NotImplementedError

    @abstractmethod
    async def holds_photo(self, key: str) -> bool:
        """Tell whether any work already names this photo.

        The answer is what turns a key the storage reissued into a defect
        report: the file behind it belongs to a work that is still live.
        """
        raise NotImplementedError


class WorkPhotoStorage(Protocol):
    """Storage port of the photo files of the gallery."""

    @abstractmethod
    async def put(self, upload: ImageUpload) -> str:
        """Store one photo and answer with the key that names it from now on.

        The key is what the database, the admin and the storefront carry; it
        is never a path of the implementation, so a second implementation
        costs no migration.
        """
        raise NotImplementedError

    @abstractmethod
    async def remove(self, key: str) -> None:
        """Drop the photo the key names, whether or not the storage still holds it.

        Implementations answer instead of raising when the file is already
        gone or cannot be dropped: the row that named it is what the
        storefront reads, and it is gone by the time this is called.
        """
        raise NotImplementedError
