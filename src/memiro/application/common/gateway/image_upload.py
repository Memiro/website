from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageUpload:
    """The photo file the owner handed a screen, on its way to the storage.

    Two storage ports carry it — the photos of a product and the photograph
    of a work — so it belongs to neither and lives on its own.
    """

    filename: str
    content: bytes
