import argparse

from memiro.adapters.db.migrations import apply_migrations
from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.django_admin.setup import run_django_command
from memiro.bootstrap.fast_api import run_api

# The admin's management commands the contour is allowed to run; a production
# image is no place for `shell`, `flush` or `sqlflush`.
ADMIN_COMMANDS = ("migrate", "ensure_superuser", "collectstatic")


# Alembic owns the domain tables and runs first; Django's own migrations own
# the service tables (auth_*, django_*) and follow. The order is here, not in
# the contour's memory.
def _apply_migrations() -> None:
    """Migrate both halves of the schema."""
    apply_migrations(Config.load().db.url)
    run_django_command(["migrate", "--no-input"])


def main() -> None:
    """Dispatch to one process of the ``memiro`` context (§11.3)."""
    parser = argparse.ArgumentParser(prog="memiro")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a service")
    run_parser.add_argument("service", choices=["api"])

    migrations_parser = subparsers.add_parser("migrations", help="manage database migrations")
    migrations_parser.add_argument("action", choices=["apply"])

    django_parser = subparsers.add_parser("django", help="run a Django management command of the admin")
    django_parser.add_argument("action", choices=ADMIN_COMMANDS)
    django_parser.add_argument("options", nargs=argparse.REMAINDER)

    args = parser.parse_args()
    if args.command == "run":
        run_api()
    elif args.command == "migrations":
        _apply_migrations()
    elif args.command == "django":
        run_django_command([args.action, *args.options])
