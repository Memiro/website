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

from memiro.seo import structured
from memiro.seo.meta import DEFAULT_OG_IMAGE, PageMeta, clamp, title
from .filters import CatalogFilters, FilterError
from .landings import landing_products, visible_landings
from .models import POPULAR_ORDERING, Category, Landing, Product

if TYPE_CHECKING:
    from django.core.paginator import Page
    from django.db.models import QuerySet
    from django.db.models.fields.files import ImageFieldFile
    from django.http import HttpRequest, HttpResponse, QueryDict

PAGE_SIZE = 12

# Ключ сортировки → (порядок выборки, подпись в селекте)
SORTS = {
    "popular": (POPULAR_ORDERING, "популярные"),
    "price": (("price", "order", "name"), "дешевле"),
    "-price": (("-price", "order", "name"), "дороже"),
    "new": (("-created_at", "order", "name"), "новинки"),
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
        for key, (_, label) in SORTS.items()
    ]


def category_covers(
    categories: list[Category],
) -> dict[int, ImageFieldFile]:
    """Обложки плиток: по одному фото на категорию, одним запросом.

    Побеждает первый по витринному порядку товар с фото — плитка
    показывает то же, что стоит первым в самой категории.
    """
    covers: dict[int, ImageFieldFile] = {}
    products = (
        Product.objects.published()
        .filter(category__in=categories)
        .exclude(photo_small="")
        .by_popularity()
    )
    for product in products:
        covers.setdefault(product.category_id, product.photo_small)
    return covers


def category_tiles(categories: list[Category]) -> list[dict[str, object]]:
    """Категории с обложками — плитки главной и корня каталога."""
    covers = category_covers(categories)
    return [
        {"category": category, "cover": covers.get(category.pk)}
        for category in categories
    ]


def catalog(request: HttpRequest) -> HttpResponse:
    """Корень каталога: одна видимая категория — сразу в неё."""
    categories = list(Category.objects.visible())
    if len(categories) == 1:
        return redirect("category", slug=categories[0].slug)
    return render(
        request,
        "catalog/index.html",
        {
            "tiles": category_tiles(categories),
            "meta": PageMeta(
                title=title("Каталог зеркал на заказ"),
                description=clamp(
                    "Каталог memiro: интерьерные зеркала на заказ по вашим "
                    "размерам. Изготовление, доставка и установка "
                    "в Санкт-Петербурге."
                ),
            ),
            "breadcrumbs": structured.home_crumbs(structured.Crumb("Каталог")),
        },
    )


def category(request: HttpRequest, slug: str) -> HttpResponse:
    category = get_object_or_404(Category.objects.visible(), slug=slug)
    base = category.products.published().select_related("category")
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
    ordering, _ = SORTS[sort_key]
    page = _page(products.order_by(*ordering), request.GET)

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
            "meta": _category_meta(category, base),
            "breadcrumbs": structured.category_crumbs(category),
            # Ссылки на посадочные с категории (ADR-0003): иначе их
            # некому обходить. Пустая посадочная отдаёт 404 — ссылки
            # на неё быть не должно
            "landings": visible_landings(category.landings.published()),
            **_pagination(request.GET, page),
        },
    )


def product(
    request: HttpRequest, category_slug: str, slug: str
) -> HttpResponse:
    product = get_object_or_404(
        Product.objects.published().select_related("category"),
        category__slug=category_slug,
        slug=slug,
    )
    specs = product.attribute_values.select_related(
        "attribute", "value_option"
    ).order_by("attribute__order", "attribute__name")
    related = (
        product.category.products.published()
        .exclude(pk=product.pk)
        .select_related("category")
        .by_popularity()[:4]
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
            "meta": _product_meta(product),
            "breadcrumbs": structured.category_crumbs(
                product.category, structured.Crumb(product.name)
            ),
            "product_jsonld": structured.product_markup(request, product),
        },
    )


def landing(request: HttpRequest, slug: str) -> HttpResponse:
    """Посадочная: категория, сужённая условиями из админки (ADR-0003).

    Единственная индексируемая фильтрация — со своим title/h1/текстом
    и self-canonical.
    """
    landing = get_object_or_404(
        Landing.objects.published().select_related("category"),
        slug=slug,
    )
    products = landing_products(landing)
    if not products.exists():
        # Пустая посадочная ведёт себя как пустая комбинация фильтров;
        # из sitemap она по той же причине выпадает
        message = "Посадочная без товаров"
        raise Http404(message)

    page = _page(products, request.GET)
    return render(
        request,
        "catalog/landing.html",
        {
            "landing": landing,
            "category": landing.category,
            "page": page,
            "canonical": _self_canonical(
                request, landing.get_absolute_url(), page
            ),
            "meta": PageMeta(
                title=landing.title,
                description=clamp(landing.description),
            ),
            "breadcrumbs": structured.category_crumbs(
                landing.category, structured.Crumb(landing.heading)
            ),
            **_pagination(request.GET, page),
        },
    )


def _category_meta(category: Category, base: QuerySet[Product]) -> PageMeta:
    """Мета категории считается по всей категории, а не по фильтрам:
    у отфильтрованных URL та же страница в индексе (ADR-0003)."""
    cheapest = base.order_by("price").values_list("price", flat=True).first()
    price = f" от {cheapest} ₽" if cheapest else ""
    return PageMeta(
        title=title(f"{category.name} на заказ в Санкт-Петербурге"),
        description=clamp(
            f"{category.name} на заказ по вашим размерам{price}. "
            "Собственное производство memiro, доставка и установка "
            "в Санкт-Петербурге."
        ),
    )


def _product_meta(product: Product) -> PageMeta:
    photo = product.main_photo
    description = product.description or (
        f"{product.name} — изготовление под заказ по вашим размерам. "
        f"Цена от {product.price} ₽, доставка и установка "
        "в Санкт-Петербурге."
    )
    return PageMeta(
        title=title(f"{product.name} — купить в Санкт-Петербурге"),
        description=clamp(description),
        image=photo.url if photo else DEFAULT_OG_IMAGE,
        og_type="product",
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
    """Canonical по ADR-0003: фильтры и сортировка → чистая категория,
    пагинация — self-canonical."""
    path = reverse("category", kwargs={"slug": category.slug})
    if filters.is_active or sort:
        return request.build_absolute_uri(path)
    return _self_canonical(request, path, page)


def _self_canonical(request: HttpRequest, path: str, page: Page) -> str:
    """Страница указывает на саму себя, номер страницы сохраняется."""
    url = request.build_absolute_uri(path)
    if page.number > 1:
        return f"{url}?page={page.number}"
    return url


def _pagination(query: QueryDict, page: Page) -> dict[str, object]:
    """Пагинация страницы каталога — общая для категории и посадочной."""
    return {
        "page_links": _page_links(query, page),
        "next_query": _query_with_page(query, page.number + 1)
        if page.has_next()
        else "",
    }


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
