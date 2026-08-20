from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import render

from .models import Work

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def works(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "content/works.html",
        {"works": Work.objects.published()},
    )
