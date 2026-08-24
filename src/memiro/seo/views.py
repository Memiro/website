"""robots.txt, собранный из базы (ADR-0003).

Параметры фильтров — это слаги атрибутов, заведённых владельцем в
админке; список запретов пересобирается сам, без правки файла руками.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpResponse
from django.urls import reverse

from memiro.catalog.filters import FILTERABLE_KINDS, PRICE_PARAMS
from memiro.catalog.models import Attribute

if TYPE_CHECKING:
    from django.http import HttpRequest

# Служебные разделы: индексировать нечего. Корзины и избранного тут
# нет намеренно — они закрыты `noindex, follow` (ADR-0005), а запрет
# обхода помешал бы роботу этот `noindex` прочитать
CLOSED_PATHS = ("/admin/", "/api/")


def filter_params() -> list[str]:
    """Параметры, порождающие дубли: сортировка, цена и слаги атрибутов.

    Спрашивается не `filters.filterable_attributes()`, и намеренно:
    здесь вопрос другой. Тот отвечает, чем сузить выдачу, — этот, какой
    параметр в адресе порождает дубль. Слаг атрибута, который фильтра
    больше не строит (тип полотна, тикет 22), выдачу не сужает, но
    вторым адресом той же страницы остаётся, и закрыть его нужно тем
    более. Категория тут тоже не спрашивается: robots.txt один на сайт.
    """
    slugs = (
        Attribute.objects.filter(kind__in=FILTERABLE_KINDS)
        .order_by("slug")
        .values_list("slug", flat=True)
        .distinct()
    )
    # Сортировка и цена — такие же параметрические дубли, как фильтр
    # по атрибуту, хотя из атрибутов и не растут
    return ["sort", *PRICE_PARAMS, *slugs]


def robots(request: HttpRequest) -> HttpResponse:
    params = filter_params()
    lines = ["User-agent: *"]
    lines += [f"Disallow: {path}" for path in CLOSED_PATHS]
    # Параметрические URL фильтров закрыты, чистые страницы
    # категорий — нет
    lines += [f"Disallow: /*?*{param}=" for param in params]
    lines.append("")
    # Clean-param — то же для Яндекса: он склеивает дубли, а не прячет
    lines.append(f"Clean-param: {'&'.join(params)}")
    lines.append("")
    lines.append(f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
