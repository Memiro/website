"""Проверка: реквизиты продавца заполнены.

Пустые реквизиты витрина не печатает — и молча оказывается сайтом без
названного продавца, а политика обработки ПД — документом без
названного оператора. Тесты этого не ловят: механика-то работает.
Поэтому о пропуске говорит `manage.py check` — там, где на него
смотрят перед выкладкой.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.checks import Warning as CheckWarning
from django.core.checks import register

from . import seller

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.apps import AppConfig

MISSING_REQUISITES = "memiro.legal.W001"


@register()
def seller_requisites_are_filled(
    # Сигнатуру диктует контракт django.core.checks
    app_configs: Sequence[AppConfig] | None = None,  # noqa: ARG001
    **kwargs: object,  # noqa: ARG001
) -> list[CheckWarning]:
    missing = seller.SELLER.missing()
    if not missing:
        return []
    return [
        CheckWarning(
            "Реквизиты продавца не заполнены: " + ", ".join(missing),
            hint=(
                "Впишите их в memiro/legal/seller.py. Без них витрина "
                "не называет продавца (п. 18 ПП РФ 2463), а политика "
                "обработки ПД — оператора (ст. 18.1 152-ФЗ)."
            ),
            id=MISSING_REQUISITES,
        )
    ]
