import os

SETTINGS_MODULE = "memiro.bootstrap.django_admin.settings"
SETTINGS_MODULE_ENV = "DJANGO_SETTINGS_MODULE"


def announce_settings() -> None:
    """Point Django at this context's settings module before anything imports it."""
    os.environ.setdefault(SETTINGS_MODULE_ENV, SETTINGS_MODULE)


def run_django_command(argv: list[str]) -> None:
    """Run one Django management command inside the admin's settings."""
    announce_settings()
    # Imported here: the module pulls in django.conf, which reads the settings
    # module the line above has just named.
    from django.core.management import execute_from_command_line  # noqa: PLC0415

    execute_from_command_line(["memiro-admin", *argv])
