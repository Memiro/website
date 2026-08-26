from dataclasses import dataclass
from typing import Any, ClassVar, dataclass_transform


@dataclass_transform(kw_only_default=True)
def app_error[T](cls: type[T]) -> type[T]:
    """Turn an exception class into a kw-only slots dataclass."""
    return dataclass(slots=True, kw_only=True)(cls)


@app_error
class AppError(Exception):
    """Base for expected business failures, mapped to 4xx responses."""

    code: ClassVar[str] = "APP_ERROR"
    message: str = "Application error"

    def __post_init__(self) -> None:
        super().__init__(self.message)

    @property
    def meta(self) -> dict[str, Any] | None:
        """Machine-readable context for the error response, if any."""
        return None
