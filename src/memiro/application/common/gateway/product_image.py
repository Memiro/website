from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ImageUpload:
    """The photo file the owner handed a screen, on its way to the storage."""

    filename: str
    content: bytes


class ProductImageStorage(Protocol):
    """Storage port of the product photo files."""

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
