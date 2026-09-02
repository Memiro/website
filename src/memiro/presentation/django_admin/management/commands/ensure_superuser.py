"""The owner's single admin account, created from the environment (decision 11).

The credentials are a deployment secret and stay out of the TOML config that
lives in git; the command is idempotent so restarting the contour is safe and
rotating the password is one environment change away.
"""

from typing import override

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from memiro.presentation.django_admin.credentials import OwnerCredentials


def ensure_superuser(credentials: OwnerCredentials) -> bool:
    """Upsert the owner's account and say whether it had to be created."""
    # Django's stock user model, named outright: the admin has one account
    # and no roles (decision 11), so there is nothing to swap it for.
    user, created = User.objects.get_or_create(username=credentials.username)
    user.is_staff = True
    user.is_superuser = True
    user.set_password(credentials.password)
    user.save()

    return created


class Command(BaseCommand):
    """Create the owner's superuser, or reset its password to the current environment."""

    help = "Ensure the owner's superuser exists with the credentials from the environment"

    @override
    def handle(self, *args: object, **options: object) -> None:
        """Upsert the single admin account; never write the password to the log."""
        credentials = OwnerCredentials.from_env()

        created = ensure_superuser(credentials)

        self.stdout.write(f"superuser {credentials.username} {'created' if created else 'updated'}")
