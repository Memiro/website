from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Final

from PIL import Image, ImageOps, UnidentifiedImageError

from memiro.application.common.gateway.product_image import StoredVariant
from memiro.application.errors.media import ImageNotProcessableError

# The widths the storefront picks from: a quarter-width card on an ordinary
# phone, a card on a desktop grid, and a half-screen tile on a doubled
# density. The original stays on the volume as the source for a second pass
# and never enters a srcset of its own.
DERIVATIVE_WIDTHS: Final = (480, 960, 1440)

# Chosen against the studio's own photographs: the step to 90 doubles the
# file without a visible difference on a mirror, the step to 75 shows on the
# frames.
WEBP_QUALITY: Final = 82


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
        for name in (key, *(_derivative_key(key, width) for width in DERIVATIVE_WIDTHS)):
            Path(self.root / name).unlink(missing_ok=True)

    def variants(self, key: str) -> list[StoredVariant]:
        """Answer with the copies this volume really holds for the photo, widest last."""
        return [
            StoredVariant(key=_derivative_key(key, width), width=width)
            for width in DERIVATIVE_WIDTHS
            if Path(self.root / _derivative_key(key, width)).is_file()
        ]


def _derivative_key(key: str, width: int) -> str:
    """Name the copy of that width the way this module always names it."""
    return f"{PurePosixPath(key).stem}-{width}w.webp"


def _derivatives(content: bytes) -> dict[int, bytes]:
    """Encode the photo at every width, in memory: a half-written set is worse than a refusal."""
    try:
        with Image.open(BytesIO(content)) as opened:
            # A camera writes the orientation into EXIF and leaves the pixels
            # alone; a copy carries no EXIF, so the rotation is applied here
            # or the storefront shows the mirror on its side.
            frame = ImageOps.exif_transpose(opened).convert("RGB")
            return {width: _encoded(frame, width) for width in DERIVATIVE_WIDTHS}
    except (UnidentifiedImageError, OSError, ValueError) as failure:
        raise ImageNotProcessableError from failure


def _encoded(frame: Image.Image, width: int) -> bytes:
    """Encode one copy no wider than the photograph itself: an upscale is bytes for nothing."""
    copy = frame.copy()
    copy.thumbnail((min(width, frame.width), frame.height), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    copy.save(buffer, format="WEBP", quality=WEBP_QUALITY, method=6)
    return buffer.getvalue()
