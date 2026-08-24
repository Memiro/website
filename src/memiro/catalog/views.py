"""Витрина каталога: список категорий, страница категории, карточка.

SEO-правила — ADR-0003: параметрические URL фильтров и сортировки
канонизируются на категорию, страницы пагинации self-canonical.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import F, Min
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from memiro.seo import structured
from memiro.seo.meta import DEFAULT_OG_IMAGE, PageMeta, clamp, title
from . import calculator, tariffs
from .filters import CatalogFilters, FilterError
from .landings import landing_products, visible_landings
from .models import POPULAR_ORDERING, Category, Landing, Product
from .tiles import catalog_root_target, catalog_tiles

if TYPE_CHECKING:
    from django.core.paginator import Page
    from django.db.models import QuerySet
    from django.db.models.expressions import Combinable
    from django.http import HttpRequest, HttpResponse, QueryDict

PAGE_SIZE = 12

# Товар без вариантов цены не имеет (ADR-0007). В сортировке по цене
# он идёт последним с обоих концов: «дешевле» — не про то, что цена
# неизвестна, а первым местом это выглядело бы именно так
CHEAPEST_FIRST = F("price").asc(nulls_last=True)
DEAREST_FIRST = F("price").desc(nulls_last=True)

# Ключ сортировки → (порядок выборки, подпись в селекте)
SORTS: dict[str, tuple[tuple[str | Combinable, ...], str]] = {
    "popular": (POPULAR_ORDERING, "популярные"),
    "price": ((CHEAPEST_FIRST, "order", "name"), "дешевле"),
    "-price": ((DEAREST_FIRST, "order", "name"), "дороже"),
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


def catalog(request: HttpRequest) -> HttpResponse:
    """Корень каталога: плитки посадочных либо редирект в категорию."""
    target = catalog_root_target()
    if target is not None:
        return redirect("category", slug=target.slug)
    return render(
        request,
        "catalog/index.html",
        {
            "tiles": catalog_tiles(),
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
            "query": _query_without(request.GET, chip.param, chip.token),
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
            "price": filters.price_control(base),
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
        Product.objects.published()
        .select_related("category")
        .prefetch_related(tariffs.product_values()),
        category__slug=category_slug,
        slug=slug,
    )
    # Характеристики — те же строки, что уже загрузил префетч расчёта:
    # второй запрос за ними отдавал бы то же самое. Порядок владельца
    # ставится в Python, раз строки в памяти
    specs = sorted(
        product.attribute_values.all(),
        key=lambda row: (row.attribute.order, row.attribute.name),
    )
    related = (
        product.category.products.published()
        .exclude(pk=product.pk)
        .select_related("category")
        .by_popularity()[:4]
    )
    # Предпосчитанные варианты в порядке, заданном владельцем; цена у
    # них уже посчитана (тикет 17). Список, а не запрос: на одном из
    # них открывается калькулятор, и второй раз за ними в базу ходить
    # незачем. Атрибут значения нужен ему же — решить, какой вариант
    # он способен показать
    variants = list(product.variants.prefetch_related("values__attribute"))
    return render(
        request,
        "catalog/product.html",
        {
            "product": product,
            "specs": specs,
            "variants": variants,
            "related": related,
            "gallery": list(product.gallery.all()),
            # Есть у товара калькулятор или нет, решают его данные:
            # изделие вне считаемого набора обходится вариантами и
            # заявкой, а числа не выдумывает (тикет 20)
            "calculator": calculator.for_product(product, variants=variants),
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
    # Min(), а не первая строка сортировки: товары без цены её не
    # задают, а в порядке сортировки они всё равно где-то стоят
    cheapest = base.aggregate(low=Min("price"))["low"]
    price = f" от {cheapest} ₽" if cheapest is not None else ""
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
    # Товар без вариантов цены не имеет — в описании её тогда нет
    price_sentence = (
        f"Цена от {product.price} ₽. " if product.has_price else ""
    )
    description = product.description or (
        f"{product.name} — изготовление под заказ по вашим размерам. "
        f"{price_sentence}Доставка и установка в Санкт-Петербурге."
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


def _query_without(query: QueryDict, param: str, token: str) -> str:
    """Querystring без одного значения фильтра и без номера страницы."""
    result = query.copy()
    result.setlist(
        param, [value for value in result.getlist(param) if value != token]
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
