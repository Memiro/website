import os
from dataclasses import dataclass
from typing import Self

from django.core.management.base import CommandError

# The owner's credentials are a deployment secret, so they arrive as
# environment variables and never through the TOML file that lives in git.
# This is the one place that reads them (§11.2).
USERNAME_ENV = "MEMIRO_ADMIN_USERNAME"
PASSWORD_ENV = "MEMIRO_ADMIN_PASSWORD"  # noqa: S105  # nosec B105  # the name of the variable, not its value


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnerCredentials:
    """What the owner signs into the admin with — one account, no roles (decision 11)."""

    username: str
    password: str

    @classmethod
    def from_env(cls) -> Self:
        """Read the owner's credentials from the environment, or refuse to guess them."""
        username = os.environ.get(USERNAME_ENV, "")
        password = os.environ.get(PASSWORD_ENV, "")
        if not username or not password:
            message = f"{USERNAME_ENV} and {PASSWORD_ENV} must both be set"
            raise CommandError(message)

        return cls(username=username, password=password)
