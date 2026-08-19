"""Витрина каталога: список категорий, страница категории, карточка.

SEO-правила — ADR-0003: параметрические URL фильтров и сортировки
канонизируются на категорию, страницы пагинации self-canonical.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .filters import CatalogFilters, FilterError
from .models import Category, Product

if TYPE_CHECKING:
    from django.core.paginator import Page
    from django.db.models import QuerySet
    from django.http import HttpRequest, HttpResponse, QueryDict

PAGE_SIZE = 12

# Ключ сортировки → порядок выборки; первый ключ — сортировка по умолчанию
SORTS = {
    "popular": ("-is_popular", "order", "name"),
    "price": ("price", "order", "name"),
    "-price": ("-price", "order", "name"),
    "new": ("-created_at", "order", "name"),
}
SORT_LABELS = {
    "popular": "популярные",
    "price": "дешевле",
    "-price": "дороже",
    "new": "новинки",
}
DEFAULT_SORT = "popular"


def _sort_options(sort_key: str) -> list[dict[str, object]]:
    """Опции селекта; у сортировки по умолчанию пустое значение,
    чтобы не плодить ?sort=popular в URL."""
    return [
        {
            "value": "" if key == DEFAULT_SORT else key,
            "label": label,
            "is_selected": key == sort_key,
        }
        for key, label in SORT_LABELS.items()
    ]


def catalog(request: HttpRequest) -> HttpResponse:
    """Корень каталога: одна видимая категория — сразу в неё."""
    categories = list(Category.objects.visible())
    if len(categories) == 1:
        return redirect("category", slug=categories[0].slug)
    return render(request, "catalog/index.html", {"categories": categories})


def category(request: HttpRequest, slug: str) -> HttpResponse:
    category = get_object_or_404(Category.objects.visible(), slug=slug)
    base = category.products.filter(is_published=True).select_related(
        "category"
    )
    try:
        filters = CatalogFilters.parse(category, request.GET)
    except FilterError as error:
        raise Http404(str(error)) from error
    products = filters.apply(base)
    if filters.is_active and not products.exists():
        message = "Пустая комбинация фильтров"
        raise Http404(message)

    sort = request.GET.get("sort") or ""
    sort_key = sort if sort in SORTS else DEFAULT_SORT
    page = _page(products.order_by(*SORTS[sort_key]), request.GET)

    applied = [
        {
            "label": chip.label,
            "query": _query_without(request.GET, chip.slug, chip.token),
        }
        for chip in filters.applied()
    ]
    return render(
        request,
        "catalog/category.html",
        {
            "category": category,
            "page": page,
            "groups": filters.groups(base),
            "applied": applied,
            "sort_options": _sort_options(sort_key),
            "canonical": _canonical(request, category, filters, sort, page),
            "page_links": _page_links(request.GET, page),
            "next_query": _query_with_page(request.GET, page.number + 1)
            if page.has_next()
            else "",
        },
    )


def product(
    request: HttpRequest, category_slug: str, slug: str
) -> HttpResponse:
    product = get_object_or_404(
        Product.objects.filter(is_published=True).select_related("category"),
        category__slug=category_slug,
        slug=slug,
    )
    specs = product.attribute_values.select_related(
        "attribute", "value_option"
    ).order_by("attribute__order", "attribute__name")
    related = (
        product.category.products.filter(is_published=True)
        .exclude(pk=product.pk)
        .select_related("category")
        .order_by("-is_popular", "order", "name")[:4]
    )
    return render(
        request,
        "catalog/product.html",
        {
            "product": product,
            "specs": specs,
            "related": related,
            "gallery": list(product.gallery.all()),
            "canonical": request.build_absolute_uri(request.path),
        },
    )


def _page(products: QuerySet[Product], query: QueryDict) -> Page:
    paginator = Paginator(products, PAGE_SIZE)
    try:
        return paginator.page(query.get("page") or 1)
    except (PageNotAnInteger, EmptyPage) as error:
        raise Http404(str(error)) from error


def _canonical(
    request: HttpRequest,
    category: Category,
    filters: CatalogFilters,
    sort: str,
    page: Page,
) -> str:
    """Canonical по ADR-0003: фасеты и сортировка → чистая категория,
    пагинация — self-canonical."""
    url = request.build_absolute_uri(
        reverse("category", kwargs={"slug": category.slug})
    )
    if filters.is_active or sort:
        return url
    if page.number > 1:
        return f"{url}?page={page.number}"
    return url


def _query_without(query: QueryDict, slug: str, token: str) -> str:
    """Querystring без одного значения фильтра и без номера страницы."""
    result = query.copy()
    result.setlist(
        slug, [value for value in result.getlist(slug) if value != token]
    )
    result.pop("page", None)
    return result.urlencode()


def _query_with_page(query: QueryDict, number: int) -> str:
    result = query.copy()
    if number > 1:
        result["page"] = str(number)
    else:
        result.pop("page", None)
    return result.urlencode()


def _page_links(query: QueryDict, page: Page) -> list[dict[str, object]]:
    return [
        {
            "number": number,
            "query": _query_with_page(query, number),
            "is_current": number == page.number,
        }
        for number in page.paginator.page_range
    ]
