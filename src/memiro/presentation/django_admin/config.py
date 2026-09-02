from dataclasses import dataclass
from typing import Any, Self

# The owner's credentials are a deployment secret, so they arrive as
# environment variables and never through the TOML file that lives in git;
# ``ensure_superuser`` is what reads them.
USERNAME_ENV = "MEMIRO_ADMIN_USERNAME"
PASSWORD_ENV = "MEMIRO_ADMIN_PASSWORD"  # noqa: S105  # nosec B105  # the name of the variable, not its value
EMAIL_ENV = "MEMIRO_ADMIN_EMAIL"


@dataclass(frozen=True, slots=True, kw_only=True)
class AdminConfig:
    """Settings of the owner's admin process — what the domain has no opinion about."""

    # Empty by default so the api process needs no ``[admin]`` section; the
    # admin process refuses to start without a real key, which is the point.
    secret_key: str = ""
    allowed_hosts: tuple[str, ...] = ()
    # collectstatic writes here; nginx serves the directory it fills.
    static_root: str = "staticfiles"

    @classmethod
    def from_section(cls, section: dict[str, Any]) -> Self:
        """Build the section from TOML, where a list of hosts really is a list."""
        defaults = cls()
        return cls(
            secret_key=section.get("secret_key", defaults.secret_key),
            allowed_hosts=tuple(section.get("allowed_hosts", defaults.allowed_hosts)),
            static_root=section.get("static_root", defaults.static_root),
        )
