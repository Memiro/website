"""URL старого сайта: карта переезда домена (тикет 09).

Строки заводит скрипт переноса (тикет 09 берёт карту у тикета 11) или
владелец руками в админке. Пустой новый путь означает 410: страницы
старого блога переезжать некуда.
"""

from __future__ import annotations

from django.db import models


def normalize_path(path: str) -> str:
    """Путь в каноничном виде: ведущий и замыкающий слеш, без хвостов."""
    path = path.strip().split("?", 1)[0].split("#", 1)[0]
    if not path:
        return "/"
    if not path.startswith("/"):
        path = f"/{path}"
    if not path.endswith("/"):
        path = f"{path}/"
    return path


class LegacyUrl(models.Model):
    """Адрес старого сайта и его судьба на новом."""

    old_path = models.CharField(
        "старый путь",
        max_length=300,
        unique=True,
        help_text="Например /mirrors/halo-moon/",
    )
    new_path = models.CharField(
        "новый путь",
        max_length=300,
        blank=True,
        help_text="Пусто — страница удалена навсегда (410)",
    )
    note = models.CharField("примечание", max_length=200, blank=True)

    class Meta:
        verbose_name = "адрес старого сайта"
        verbose_name_plural = "адреса старого сайта"
        ordering = ("old_path",)

    def __str__(self) -> str:
        return f"{self.old_path} → {self.new_path or '410'}"

    def save(self, *args: object, **kwargs: object) -> None:
        self.old_path = normalize_path(self.old_path)
        if self.new_path:
            self.new_path = normalize_path(self.new_path)
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @property
    def is_gone(self) -> bool:
        return not self.new_path
