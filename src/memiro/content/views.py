from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

from memiro.seo import structured
from memiro.seo.meta import PageMeta, clamp, title
from .models import Work

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def works(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "content/works.html",
        {
            "works": Work.objects.published(),
            "meta": PageMeta(
                title=title("Наши работы"),
                description=clamp(
                    "Фотографии зеркал memiro, установленных у клиентов "
                    "в Санкт-Петербурге: реальные интерьеры, а не рендеры."
                ),
            ),
            "breadcrumbs": structured.home_crumbs(
                structured.Crumb("Наши работы")
            ),
        },
    )
