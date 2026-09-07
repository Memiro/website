from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class InvalidLandingSlugError(AppError):
    """Raised when a landing would carry no public address at all."""

    code: ClassVar[str] = "INVALID_LANDING_SLUG"
    message: str = "A landing needs a public address"


@app_error
class InvalidLandingNarrowingError(AppError):
    """Raised when the narrowing of a landing is not one the sidebar could build.

    One code for every shape of the same fault — nothing to narrow by, more
    attributes than a landing may carry, a value of another category or of an
    attribute the sidebar does not offer, and a whole dictionary listed at
    once — because the owner's next move is the same: choose the values the
    page really stands for.
    """

    code: ClassVar[str] = "INVALID_LANDING_NARROWING"
    message: str = "A landing narrowing is invalid"
