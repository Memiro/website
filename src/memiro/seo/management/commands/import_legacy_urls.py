"""Загрузка карты переезда, которую отдаёт скрипт переноса (тикет 11).

Формат файла:

    {
      "redirects": {"/mirrors/halo-moon/": "/catalog/zerkala/halo-moon/"},
      "gone": ["/2023/01/statya/"]
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from django.core.management.base import BaseCommand, CommandError

from memiro.seo.models import LegacyUrl, normalize_path

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    help = "Загружает карту старых URL (301/410) из JSON-файла"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("path", help="JSON-файл с картой переезда")

    def handle(self, *args: object, **options: str) -> None:  # noqa: ARG002
        source = Path(options["path"])
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            message = f"Не прочитать карту {source}: {error}"
            raise CommandError(message) from error

        rules = {
            normalize_path(old): normalize_path(new)
            for old, new in data.get("redirects", {}).items()
        }
        rules.update({normalize_path(old): "" for old in data.get("gone", ())})

        for old_path, new_path in rules.items():
            LegacyUrl.objects.update_or_create(
                old_path=old_path,
                defaults={"new_path": new_path},
            )
        self.stdout.write(f"Загружено правил: {len(rules)}")
