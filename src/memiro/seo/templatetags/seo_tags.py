"""Шаблонные теги SEO: печать JSON-LD и абсолютные URL для OG."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from django import template
from django.templatetags.static import static
from django.utils.safestring import SafeString

from memiro.seo import structured
from memiro.seo.absolute import absolute_uri

if TYPE_CHECKING:
    from django.template.context import RequestContext

register = template.Library()

# Символы, которыми можно разорвать <script> изнутри строки JSON
SCRIPT_UNSAFE = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"}


@register.simple_tag
def jsonld(data: dict[str, Any] | None) -> SafeString:
    """Блок разметки; пустые данные не печатают пустой script."""
    if not data:
        return SafeString("")
    payload = json.dumps(data, ensure_ascii=False)
    for char, escaped in SCRIPT_UNSAFE.items():
        payload = payload.replace(char, escaped)
    # HTML-экранирование испортило бы JSON, поэтому строка собирается
    # вручную: разорвать script её содержимое уже не может
    return SafeString(  # nosec B703
        f'<script type="application/ld+json">{payload}</script>'
    )


@register.simple_tag(takes_context=True)
def breadcrumbs_jsonld(context: RequestContext) -> SafeString:
    """BreadcrumbList из крошек контекста — представлению её не собирать."""
    return jsonld(
        structured.breadcrumb_list(
            context["request"], context.get("breadcrumbs") or []
        )
    )


@register.simple_tag(takes_context=True)
def absolute(context: RequestContext, url: str) -> str:
    """URL для OG: путь медиа берётся как есть, остальное — из статики."""
    if not url:
        return ""
    path = url if url.startswith(("/", "http")) else static(url)
    return absolute_uri(context["request"], path)
