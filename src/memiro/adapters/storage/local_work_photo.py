import asyncio
from pathlib import PurePosixPath
from typing import override
from uuid import uuid4

import structlog

from memiro.adapters.storage.config import MediaConfig
from memiro.adapters.storage.photo_files import PhotoFiles
from memiro.application.common.gateway.image_upload import ImageUpload
from memiro.application.common.gateway.work import WorkPhotoStorage
from memiro.application.common.input_limits import IMAGE_EXTENSIONS
from memiro_common.logger import Logger

logger: Logger = structlog.get_logger(__name__)


class LocalWorkPhotoStorage(WorkPhotoStorage):
    """Photos of the gallery as files on the same media volume the edge serves."""

    def __init__(self, config: MediaConfig) -> None:
        """Keep the directory this process writes photos into."""
        self._files = PhotoFiles(root=config.root)

    @override
    async def put(self, upload: ImageUpload) -> str:
        """Write the photo and the copies made from it, off the event loop."""
        key = f"{uuid4().hex}.{_extension(upload.filename)}"
        await asyncio.to_thread(self._files.write, key, upload.content)
        return key

    @override
    async def remove(self, key: str) -> None:
        """Unlink the photo and everything made from it, off the event loop, warning instead of raising."""
        await asyncio.to_thread(self._unlink, key)

    def _unlink(self, key: str) -> None:
        """Drop the files; a file this process cannot drop is litter, not an answer to the owner."""
        try:
            self._files.unlink(key)
        except OSError as failure:
            logger.warning("A work photo stayed on the storage", key=key, error=type(failure).__name__)


def _extension(filename: str) -> str:
    """Read the extension the key will end with, refusing a name no form validated."""
    extension = PurePosixPath(filename).suffix.lstrip(".").lower()
    if extension not in IMAGE_EXTENSIONS:
        # What a photo is, is decided once, by the application form; the
        # storage only guards the file name it is about to write to a disk.
        msg = f"A work photo is one of {', '.join(IMAGE_EXTENSIONS)}, not {filename!r}"
        raise RuntimeError(msg)
    return extension
