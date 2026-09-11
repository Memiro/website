from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class ImageNotProcessableError(AppError):
    """Raised when the uploaded file cannot be read as a photograph.

    The extension is all the form knows about a file; whether the bytes are a
    picture at all is learnt by the storage, when it makes the copies the
    storefront serves.
    """

    code: ClassVar[str] = "IMAGE_NOT_PROCESSABLE"
    message: str = "The uploaded file cannot be read as a photograph"
