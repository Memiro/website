from abc import abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from memiro.application.common.gateway.image_upload import ImageUpload


@dataclass(frozen=True, slots=True)
class StoredVariant:
    """One narrower copy of a stored photo: the key naming it and the width it was made at.

    How many copies a photo has is a fact about delivering bytes, not
    about mirrors, so it lives here and not in the domain.
    """

    key: str
    width: int


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

    @abstractmethod
    async def variants(self, keys: Sequence[str]) -> Mapping[str, list[StoredVariant]]:
        """Answer with the narrower copies the storage holds for each of the keys.

        A photo the storage made no copies of answers with an empty list: the
        reading side still shows it, at the one size there is.
        """
        raise NotImplementedError
