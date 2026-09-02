"""The owner's single admin account, created from the environment (decision 11).

The credentials are a deployment secret and stay out of the TOML config that
lives in git; the command is idempotent so restarting the contour is safe and
rotating the password is one environment change away.
"""

import os
from typing import override

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from memiro.presentation.django_admin.config import EMAIL_ENV, PASSWORD_ENV, USERNAME_ENV


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

        # Django's stock user model, named outright: the admin has one account
        # and no roles (decision 11), so there is nothing to swap it for.
        user, created = User.objects.get_or_create(username=username)
        # An address the environment does not carry is not an empty address:
        # the command runs on every start and must not erase what it finds.
        user.email = os.environ.get(EMAIL_ENV, user.email)
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        self.stdout.write(f"superuser {username} {'created' if created else 'updated'}")
