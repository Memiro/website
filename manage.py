#!/usr/bin/env python
import os
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memiro.settings")
    # settings-модуль должен попасть в окружение до импорта Django
    from django.core.management import (  # noqa: PLC0415
        execute_from_command_line,
    )

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
