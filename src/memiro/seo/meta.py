"""Метатеги страницы: один источник для title, description и OG.

Каждое представление кладёт в контекст `PageMeta`; шаблон `base.html`
разворачивает её в `<title>`, description, OG- и twitter-теги. Страницы
без своей меты получают дефолт из контекст-процессора `seo.defaults`.
"""

from __future__ import annotations

from dataclasses import dataclass

SITE_NAME = "memiro"

# Витринный OG-кадр по умолчанию: тот же hero, что на главной
DEFAULT_OG_IMAGE = "img/hero-1.jpg"

# Корзина и страницы ошибок в индекс не идут, но ссылки с них
# поисковик обходит
NOINDEX = "noindex, follow"


@dataclass(frozen=True)
class PageMeta:
    """Уникальные метатеги одной страницы."""

    title: str
    description: str
    # Путь статики (`img/...`) или URL медиа — абсолютным его делает
    # шаблонный тег `absolute`
    image: str = DEFAULT_OG_IMAGE
    og_type: str = "website"
    # Пусто — страница индексируется
    robots: str = ""


def title(text: str) -> str:
    """Заголовок страницы с общим хвостом сайта."""
    return f"{text} — {SITE_NAME}"


def clamp(text: str, limit: int = 160) -> str:
    """Description под длину сниппета: обрезка по границе слова."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"
