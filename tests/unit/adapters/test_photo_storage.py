"""The local photo storage against the volume: what it leaves behind, and what it takes away."""

from pathlib import Path

import pytest
from PIL import Image

from memiro.adapters.storage.config import MediaConfig
from memiro.adapters.storage.local_product_image import LocalProductImageStorage
from memiro.adapters.storage.photo_files import DERIVATIVE_WIDTHS
from memiro.application.common.gateway.image_upload import ImageUpload
from memiro.application.errors.media import ImageNotProcessableError
from tests.common.photograph import PHOTOGRAPH_WIDTH, photograph

PHOTO = photograph()

# A file with an extension a form accepts and bytes no decoder reads.
NOT_A_PHOTOGRAPH = b"a receipt, saved as .jpg"


def _storage(root: Path) -> LocalProductImageStorage:
    """Build the storage over one throwaway volume."""
    return LocalProductImageStorage(MediaConfig(root=root))


def _names(root: Path) -> list[str]:
    """Read what the volume holds, by name."""
    return sorted(path.name for path in root.iterdir()) if root.exists() else []


def _prime(root: Path, name: str) -> None:
    """Put a photo on the volume the way the storage did before it made copies."""
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_bytes(PHOTO)


def _read(root: Path, name: str) -> bytes:
    """Read one file of the volume."""
    return (root / name).read_bytes()


def _widths(root: Path, key: str) -> list[int]:
    """Read the width every copy of the photo was really encoded at."""
    widths: list[int] = []
    for width in DERIVATIVE_WIDTHS:
        with Image.open(root / f"{Path(key).stem}-{width}w.webp") as copy:
            assert copy.format == "WEBP"
            widths.append(copy.width)
    return widths


async def test_a_stored_photograph_is_kept_beside_a_copy_for_every_width(tmp_path: Path) -> None:
    """The owner uploads one file, and the storefront gets a choice of widths."""
    storage = _storage(tmp_path)

    key = await storage.put(ImageUpload(filename="mirror.jpg", content=PHOTO))

    assert _read(tmp_path, key) == PHOTO
    assert _names(tmp_path) == sorted([key, *(f"{Path(key).stem}-{width}w.webp" for width in DERIVATIVE_WIDTHS)])


async def test_every_copy_is_a_webp_no_wider_than_the_photograph(tmp_path: Path) -> None:
    """A copy is what its name promises: WebP of that width, and never an upscale."""
    storage = _storage(tmp_path)

    key = await storage.put(ImageUpload(filename="mirror.jpg", content=PHOTO))

    assert _widths(tmp_path, key) == [min(width, PHOTOGRAPH_WIDTH) for width in DERIVATIVE_WIDTHS]


async def test_the_storage_answers_with_the_copies_it_holds(tmp_path: Path) -> None:
    """The reading side asks what there is instead of guessing at names."""
    storage = _storage(tmp_path)
    key = await storage.put(ImageUpload(filename="mirror.jpg", content=PHOTO))

    variants = await storage.variants([key])

    assert [variant.width for variant in variants[key]] == list(DERIVATIVE_WIDTHS)


async def test_a_photograph_without_copies_is_answered_with_an_empty_list(tmp_path: Path) -> None:
    """A photo uploaded before the copies existed is still a photo the storefront shows."""
    storage = _storage(tmp_path)
    _prime(tmp_path, "legacy.jpg")

    variants = await storage.variants(["legacy.jpg"])

    assert variants["legacy.jpg"] == []


async def test_dropping_a_photograph_takes_everything_made_from_it(tmp_path: Path) -> None:
    """Removing one photo empties the volume of it: nothing is left to fill the disk."""
    storage = _storage(tmp_path)
    key = await storage.put(ImageUpload(filename="mirror.jpg", content=PHOTO))

    await storage.remove(key)

    assert _names(tmp_path) == []


async def test_dropping_a_photograph_without_copies_says_nothing(tmp_path: Path) -> None:
    """A photo uploaded before the copies existed is removed as quietly as any other."""
    storage = _storage(tmp_path)
    _prime(tmp_path, "legacy.jpg")

    await storage.remove("legacy.jpg")

    assert _names(tmp_path) == []


async def test_a_file_that_is_no_photograph_is_refused_and_leaves_nothing_behind(tmp_path: Path) -> None:
    """A file no decoder reads never becomes a photo of two sorts: IMAGE_NOT_PROCESSABLE."""
    storage = _storage(tmp_path)

    with pytest.raises(ImageNotProcessableError):
        await storage.put(ImageUpload(filename="mirror.jpg", content=NOT_A_PHOTOGRAPH))

    assert _names(tmp_path) == []
