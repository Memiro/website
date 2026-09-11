"""Real photographs for the slices that store them: the storage now looks inside the file."""

from io import BytesIO

from PIL import Image

# Wide enough that the storage has something to narrow down to every width it
# makes a copy at, small enough to stay a handful of kilobytes in a fixture.
PHOTOGRAPH_WIDTH = 1600
PHOTOGRAPH_HEIGHT = 1200


def photograph(*, width: int = PHOTOGRAPH_WIDTH, height: int = PHOTOGRAPH_HEIGHT, shade: int = 120) -> bytes:
    """Encode one plain JPEG of that size: what a camera hands the owner, without the camera."""
    buffer = BytesIO()
    Image.new("RGB", (width, height), (shade, shade, shade)).save(buffer, format="JPEG")
    return buffer.getvalue()
