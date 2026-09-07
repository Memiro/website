import asyncio
from pathlib import Path, PurePosixPath
from typing import override
from uuid import uuid4

import structlog

from memiro.adapters.storage.config import MediaConfig
from memiro.application.common.gateway.product_image import ImageUpload, ProductImageStorage
from memiro.application.common.input_limits import IMAGE_EXTENSIONS
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class LocalProductImageStorage(ProductImageStorage):
    """Product photos as files in one directory of the media volume the edge serves."""

    def __init__(self, config: MediaConfig) -> None:
        """Keep the directory this process writes photos into."""
        self._root = config.root

    @override
    async def put(self, upload: ImageUpload) -> str:
        """Write the photo under a key of the storage's own making, off the event loop."""
        key = f"{uuid4().hex}.{_extension(upload.filename)}"
        await asyncio.to_thread(self._write, key, upload.content)
        return key

    @override
    async def remove(self, key: str) -> None:
        """Unlink the file the key names, off the event loop, warning instead of raising."""
        await asyncio.to_thread(self._unlink, key)

    def _write(self, key: str, content: bytes) -> None:
        """Put one file into the directory, creating it on the first photo of a fresh volume."""
        self._root.mkdir(parents=True, exist_ok=True)
        Path(self._root / key).write_bytes(content)

    def _unlink(self, key: str) -> None:
        """Drop one file; a file this process cannot drop is litter, not an answer to the owner."""
        try:
            Path(self._root / key).unlink(missing_ok=True)
        except OSError as failure:
            logger.warning("A product photo stayed on the storage", key=key, error=type(failure).__name__)


def _extension(filename: str) -> str:
    """Read the extension the key will end with, refusing a name no form validated."""
    extension = PurePosixPath(filename).suffix.lstrip(".").lower()
    if extension not in IMAGE_EXTENSIONS:
        # What a photo is, is decided once, by the application form; the
        # storage only guards the file name it is about to write to a disk.
        msg = f"A product photo is one of {', '.join(IMAGE_EXTENSIONS)}, not {filename!r}"
        raise RuntimeError(msg)
    return extension
