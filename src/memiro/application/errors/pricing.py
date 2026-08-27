from typing import ClassVar

from memiro_common.errors import AppError, app_error


@app_error
class PricingSettingsNotFoundError(AppError):
    """Raised when the site has no pricing settings row to calculate against."""

    code: ClassVar[str] = "PRICING_SETTINGS_NOT_FOUND"
    message: str = "Pricing settings not found"
