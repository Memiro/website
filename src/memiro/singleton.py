"""Строка одна на сайт: модель и её раздел админки.

Такие данные владельца уже есть у порогов расчёта, а с тикета 01 —
и у контактов студии. Правило у них общее: вторая строка была бы
второй правдой, поэтому её негде завести и нечем удалить.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from django.contrib import admin
from django.db import models

if TYPE_CHECKING:
    from django.http import HttpRequest


class SingletonModel(models.Model):
    """Единственная строка: сохранение всегда правит её же."""

    SINGLETON_PK = 1

    class Meta:
        abstract = True

    def save(self, *args: object, **kwargs: object) -> None:
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def load(cls) -> Self:
        """Строка из базы; без неё — пустая, а не падение.

        Витрина с пустыми полями некрасива, но жива: сломанная
        страница хуже страницы без телефона.
        """
        # `_default_manager`, а не `objects`: у абстрактной модели
        # своего менеджера нет, а у наследников он зовётся по-разному
        row: Self | None = cls._default_manager.first()
        return row or cls()


class SingletonAdmin(admin.ModelAdmin):
    """Раздел одной строки: её правят, а не заводят и не удаляют."""

    def has_add_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
    ) -> bool:
        return not self.model._default_manager.exists()  # noqa: SLF001

    def has_delete_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: models.Model | None = None,  # noqa: ARG002
    ) -> bool:
        return False
