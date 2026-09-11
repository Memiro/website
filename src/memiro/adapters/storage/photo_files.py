from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Final

from PIL import Image, ImageOps, UnidentifiedImageError

from memiro.adapters.storage.errors import ImageNotProcessableError
from memiro.application.common.gateway.product_image import StoredVariant

# The widths the storefront picks from: a quarter-width card on an ordinary
# phone, a card on a desktop grid, and a half-screen tile on a doubled
# density. The original stays on the volume as the source for a second pass
# and never enters a srcset of its own.
DERIVATIVE_WIDTHS: Final = (480, 960, 1440)

# The usual trade-off point for photographs: visually lossless on a mirror
# at a fraction of the bytes. Raise it only against a real comparison.
WEBP_QUALITY: Final = 82

_DERIVATIVE_SUFFIX: Final = "w.webp"


@dataclass(frozen=True, slots=True)
class PhotoFiles:
    """One media volume: the photo the owner uploaded and the copies made from it.

    The naming of the copies is this module's own business — the key the
    database carries stays one opaque string, as the storage ports promise.
    """

    root: Path

    def write(self, key: str, content: bytes) -> None:
        """Put the photo and its copies on the volume, or refuse a file that is no photo."""
        derivatives = _derivatives(content)
        self.root.mkdir(parents=True, exist_ok=True)
        Path(self.root / key).write_bytes(content)
        for width, image in derivatives.items():
            Path(self.root / _derivative_key(key, width)).write_bytes(image)

    def unlink(self, key: str) -> None:
        """Drop the photo and everything that was made from it, each tolerant of being gone."""
        for path in [self.root / key, *self._copies(key)]:
            Path(path).unlink(missing_ok=True)

    def variants(self, key: str) -> list[StoredVariant]:
        """Answer with the copies this volume really holds for the photo, widest last.

        The width is read from the name the copy was written under, and a copy
        is only ever written under the width it was really encoded at: a
        storefront told "1440w" would otherwise pick a narrower picture than
        the place it is filling.
        """
        return sorted(
            (StoredVariant(key=path.name, width=_width_of(path.name)) for path in self._copies(key)),
            key=lambda variant: variant.width,
        )

    def _copies(self, key: str) -> list[Path]:
        """Find every copy this volume holds of the photo, whatever widths they were made at."""
        return list(self.root.glob(f"{PurePosixPath(key).stem}-*{_DERIVATIVE_SUFFIX}"))


def _derivative_key(key: str, width: int) -> str:
    """Name the copy of that width the way this module always names it."""
    return f"{PurePosixPath(key).stem}-{width}{_DERIVATIVE_SUFFIX}"


def is_derivative(name: str) -> bool:
    """Answer whether this file is a copy this module made, and not a photo somebody uploaded."""
    if not name.endswith(_DERIVATIVE_SUFFIX):
        return False
    return name.removesuffix(_DERIVATIVE_SUFFIX).rsplit("-", maxsplit=1)[-1].isdigit()


def _width_of(name: str) -> int:
    """Read back the width a copy was written under."""
    return int(name.removesuffix(_DERIVATIVE_SUFFIX).rsplit("-", maxsplit=1)[1])


def _derivatives(content: bytes) -> dict[int, bytes]:
    """Encode the photo at every width, in memory: a half-written set is worse than a refusal."""
    try:
        with Image.open(BytesIO(content)) as opened:
            # A camera writes the orientation into EXIF and leaves the pixels
            # alone; a copy carries no EXIF, so the rotation is applied here
            # or the storefront shows the mirror on its side.
            frame = ImageOps.exif_transpose(opened).convert("RGB")
            # A photo narrower than a width of the set gets one copy at its own
            # width instead: an upscale is bytes for nothing, and a name is a
            # promise about pixels.
            return {width: _encoded(frame, width) for width in {min(width, frame.width) for width in DERIVATIVE_WIDTHS}}
    except (UnidentifiedImageError, OSError, ValueError) as failure:
        raise ImageNotProcessableError from failure


def reads_as_a_photograph(content: bytes) -> bool:
    """Answer whether the storage would be able to make copies of this file."""
    try:
        _derivatives(content)
    except ImageNotProcessableError:
        return False
    return True


def _encoded(frame: Image.Image, width: int) -> bytes:
    """Encode one copy of exactly that width."""
    copy = frame.copy()
    copy.thumbnail((width, frame.height), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    copy.save(buffer, format="WEBP", quality=WEBP_QUALITY, method=6)
    return buffer.getvalue()
