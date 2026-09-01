from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class ConsentRequiredError(AppError):
    """Raised when a visitor submits an inquiry without personal-data consent."""

    code: ClassVar[str] = "CONSENT_REQUIRED"
    message: str = "Consent is required"


@app_error
class EmptyInquiryError(AppError):
    """Raised when a selection inquiry has no positions."""

    code: ClassVar[str] = "EMPTY_INQUIRY"
    message: str = "A selection inquiry needs at least one item"


@app_error
class InquirySourceNotAcceptedError(AppError):
    """Raised when a new inquiry uses a historical-only source."""

    code: ClassVar[str] = "INQUIRY_SOURCE_NOT_ACCEPTED"
    message: str = "This inquiry source is not accepted"


@app_error
class InvalidPhoneError(AppError):
    """Raised when a visitor's telephone number is not one the studio could dial."""

    code: ClassVar[str] = "INVALID_PHONE"
    message: str = "A phone number must be 10 to 15 digits"


@app_error
class InvalidInquiryContentsError(AppError):
    """Raised when source-specific inquiry fields disagree with the source."""

    code: ClassVar[str] = "INVALID_INQUIRY_CONTENTS"
    message: str = "Inquiry contents do not match its source"
