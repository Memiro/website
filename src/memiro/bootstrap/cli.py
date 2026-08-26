import argparse

from memiro.adapters.db.migrations import apply_migrations
from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.fast_api import run_api


def main() -> None:
    """Dispatch to one process of the ``memiro`` context (§11.3)."""
    parser = argparse.ArgumentParser(prog="memiro")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a service")
    run_parser.add_argument("service", choices=["api"])

    migrations_parser = subparsers.add_parser("migrations", help="manage database migrations")
    migrations_parser.add_argument("action", choices=["apply"])

    args = parser.parse_args()
    if args.command == "run":
        run_api()
    elif args.command == "migrations":
        config = Config.load()
        apply_migrations(config.db.url)
