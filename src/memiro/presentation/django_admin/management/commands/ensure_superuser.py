"""The owner's single admin account, created from the environment (decision 11).

The credentials are a deployment secret and stay out of the TOML config that
lives in git; the command is idempotent so restarting the contour is safe and
rotating the password is one environment change away.
"""

import os
from typing import override

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

USERNAME_ENV = "MEMIRO_ADMIN_USERNAME"
PASSWORD_ENV = "MEMIRO_ADMIN_PASSWORD"  # noqa: S105  # nosec B105  # the name of the variable, not its value
EMAIL_ENV = "MEMIRO_ADMIN_EMAIL"


class Command(BaseCommand):
    """Create the owner's superuser, or reset its password to the current environment."""

    help = "Ensure the owner's superuser exists with the credentials from the environment"

    @override
    def handle(self, *args: object, **options: object) -> None:
        """Upsert the single admin account; never write the password to the log."""
        username = os.environ.get(USERNAME_ENV, "")
        password = os.environ.get(PASSWORD_ENV, "")
        if not username or not password:
            message = f"{USERNAME_ENV} and {PASSWORD_ENV} must both be set"
            raise CommandError(message)

        users = get_user_model().objects
        user, created = users.get_or_create(username=username)
        # An address the environment does not carry is not an empty address:
        # the command runs on every start and must not erase what it finds.
        user.email = os.environ.get(EMAIL_ENV, user.email)
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        self.stdout.write(f"superuser {username} {'created' if created else 'updated'}")
