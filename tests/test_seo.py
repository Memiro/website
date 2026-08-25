"""SEO-базис (тикет 09): мета, JSON-LD, посадочные, sitemap, переезд."""

from __future__ import annotations

import json
import re
from datetime import time
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    Landing,
    LandingCondition,
    Product,
    ProductAttribute,
)
from memiro.catalog.views import PAGE_SIZE
from memiro.content.models import Review, SiteContacts
from memiro.seo.models import LegacyUrl

HALO_PRICE = 11795
DAYS_IN_WEEK = 7

JSONLD = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)


def blocks(html: str) -> list[dict[str, Any]]:
    """Разметка страницы, разобранная обратно в словари."""
    return [json.loads(match) for match in JSONLD.findall(html)]


def block_of(html: str, kind: str) -> dict[str, Any]:
    found = [item for item in blocks(html) if item["@type"] == kind]
    assert found, f"нет блока {kind}"
    return found[0]


def meta_content(html: str, name: str) -> str:
    match = re.search(
        rf'<meta (?:name|property)="{re.escape(name)}" content="([^"]*)"',
        html,
    )
    assert match, f"нет метатега {name}"
    return match.group(1)


def title_of(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html)
    assert match, "нет заголовка страницы"
    return match.group(1)


def page_html(client: Client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


@pytest.fixture
def shop(db: None) -> SimpleNamespace:
    """Категория «Зеркала» с двумя товарами и посадочной «с подсветкой»."""
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    forma = Attribute.objects.create(
        category=category, name="Форма", slug="forma"
    )
    krugloe = AttributeValue.objects.create(attribute=forma, value="Круглое")
    podsvetka = Attribute.objects.create(
        category=category,
        name="Подсветка",
        slug="podsvetka",
        kind=Attribute.Kind.BOOLEAN,
    )
    halo = Product.objects.create(
        category=category,
        name="Halo Moon",
        slug="halo-moon",
        price=11795,
        article="2850",
        description="Круглое зеркало с тёплой подсветкой по контуру.",
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=halo, attribute=forma, value_option=krugloe
    )
    ProductAttribute.objects.create(
        product=halo, attribute=podsvetka, value_bool=True
    )
    view_match = Product.objects.create(
        category=category,
        name="View Match",
        slug="view-match",
        price=8352,
        is_published=True,
    )
    ProductAttribute.objects.create(
        product=view_match, attribute=podsvetka, value_bool=False
    )
    landing = Landing.objects.create(
        category=category,
        slug="zerkala-s-podsvetkoy",
        title="Зеркала с подсветкой на заказ — memiro",
        heading="Зеркала с подсветкой",
        description="Зеркала с подсветкой на заказ в Санкт-Петербурге.",
        text="Подсветка по контуру не слепит и даёт ровный свет.",
        is_published=True,
    )
    LandingCondition.objects.create(
        landing=landing, attribute=podsvetka, value_bool=True
    )
    return SimpleNamespace(
        category=category,
        podsvetka=podsvetka,
        forma=forma,
        krugloe=krugloe,
        halo=halo,
        view_match=view_match,
        landing=landing,
    )


# --- Метатеги и OG ---------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/",
        "/catalog/zerkala/",
        "/catalog/zerkala/halo-moon/",
        "/zerkala-s-podsvetkoy/",
        "/works/",
        "/about/",
        "/delivery/",
        "/contacts/",
    ],
)
def test_every_page_has_title_description_and_og(
    client: Client, shop: SimpleNamespace, url: str
) -> None:
    html = page_html(client, url)

    assert "<title>" in html
    assert meta_content(html, "description")
    assert meta_content(html, "og:title")
    assert meta_content(html, "og:description")
    assert meta_content(html, "og:url").endswith(url)
    assert meta_content(html, "og:image").startswith("http")


def test_titles_and_descriptions_are_unique(
    client: Client, shop: SimpleNamespace
) -> None:
    urls = ("/", "/catalog/zerkala/", "/catalog/zerkala/halo-moon/", "/works/")
    pages = [page_html(client, url) for url in urls]

    titles = [title_of(html) for html in pages]
    descriptions = [meta_content(html, "description") for html in pages]

    assert len(set(titles)) == len(urls)
    assert len(set(descriptions)) == len(urls)


def test_product_og_image_is_its_own_photo(
    client: Client, shop: SimpleNamespace
) -> None:
    shop.halo.photo_large = "products/large/halo.jpg"
    shop.halo.save()

    html = page_html(client, "/catalog/zerkala/halo-moon/")

    assert meta_content(html, "og:image").endswith(
        "/media/products/large/halo.jpg"
    )


def test_cart_is_noindex(client: Client, shop: SimpleNamespace) -> None:
    assert meta_content(page_html(client, "/cart/"), "robots") == (
        "noindex, follow"
    )


# --- JSON-LD ---------------------------------------------------------


def test_product_jsonld_carries_offer_in_rubles(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/halo-moon/")

    product = block_of(html, "Product")
    offer = product["offers"]

    assert product["name"] == "Halo Moon"
    assert product["sku"] == "2850"
    assert offer["priceCurrency"] == "RUB"
    # Цена товара — стоимость минимальной конфигурации, витрина
    # показывает её как «от X ₽»: точной ценой её объявлять нельзя
    assert offer["@type"] == "AggregateOffer"
    assert offer["lowPrice"] == HALO_PRICE
    assert offer["url"].endswith("/catalog/zerkala/halo-moon/")


def test_breadcrumbs_jsonld_matches_visible_crumbs(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/halo-moon/")

    crumbs = block_of(html, "BreadcrumbList")["itemListElement"]

    assert [item["name"] for item in crumbs] == [
        "Главная",
        "Каталог",
        "Зеркала",
        "Halo Moon",
    ]
    assert [item["position"] for item in crumbs] == [1, 2, 3, 4]
    # У текущей страницы ссылки нет
    assert "item" not in crumbs[-1]


def test_home_has_no_breadcrumbs(
    client: Client, shop: SimpleNamespace
) -> None:
    """Одна ступень цепочкой не является — разметки на главной нет."""
    html = page_html(client, "/")

    assert not [
        item for item in blocks(html) if item["@type"] == "BreadcrumbList"
    ]


def test_local_business_has_address(
    client: Client, shop: SimpleNamespace
) -> None:
    business = block_of(page_html(client, "/contacts/"), "LocalBusiness")

    assert business["address"]["addressLocality"] == "Санкт-Петербург"
    assert business["address"]["streetAddress"] == (
        "Александра Матросова, 4к2ж"
    )
    assert business["telephone"]
    assert business["image"].startswith("http")


def test_hours_appear_only_when_set(
    client: Client, shop: SimpleNamespace
) -> None:
    """Выдуманного расписания в разметке не бывает — как и пустого контакта."""
    assert "openingHoursSpecification" not in block_of(
        page_html(client, "/contacts/"), "LocalBusiness"
    )

    contacts = SiteContacts.load()
    contacts.opens = time(10, 0)
    contacts.closes = time(20, 0)
    contacts.save()

    business = block_of(page_html(client, "/contacts/"), "LocalBusiness")

    hours = business["openingHoursSpecification"][0]
    assert len(hours["dayOfWeek"]) == DAYS_IN_WEEK
    assert hours["opens"] == "10:00"
    assert hours["closes"] == "20:00"


def test_empty_contact_is_not_named_in_markup(
    client: Client, shop: SimpleNamespace
) -> None:
    """Пустой телефон в разметке — то же враньё, что выдуманные часы."""
    contacts = SiteContacts.load()
    contacts.phone = ""
    contacts.email = ""
    contacts.vk = ""
    contacts.avito = ""
    contacts.save()

    business = block_of(page_html(client, "/contacts/"), "LocalBusiness")

    assert "telephone" not in business
    assert "email" not in business
    assert "sameAs" not in business


def test_max_placeholder_is_not_a_profile_in_markup(
    client: Client, shop: SimpleNamespace
) -> None:
    """Тикет 08: заглушка вместо профиля — то же враньё, что пустой телефон.

    «ВКонтакте» здесь заполнен нарочно: с пустым `sameAs` ключа не было
    бы вовсе и утечка MAX прошла бы мимо теста.
    """
    contacts = SiteContacts.load()
    contacts.max_link = "https://max.ru/"
    contacts.vk = "https://vk.com/memirospb"
    contacts.avito = ""
    contacts.save()

    business = block_of(page_html(client, "/contacts/"), "LocalBusiness")

    assert business["sameAs"] == ["https://vk.com/memirospb"]


def test_rating_never_appears_while_reviews_are_hidden(
    client: Client, shop: SimpleNamespace
) -> None:
    """Тикет 06: разметка и блок отзывов ездят только вместе.

    Заявленный рейтинг на странице без отзывов — нарушение правил
    и Яндекса, и Google, и стоит оно расширенного сниппета целиком.
    """
    Review.objects.create(
        author="Анна",
        text="Отличное зеркало",
        source="Avito",
        rating=5,
        is_published=True,
    )

    # Разметка шоурума печатается на обеих страницах — рейтинга нет нигде
    for route in ("/", "/contacts/"):
        assert "aggregateRating" not in block_of(
            page_html(client, route), "LocalBusiness"
        )


def test_jsonld_cannot_break_out_of_script(
    client: Client, shop: SimpleNamespace
) -> None:
    shop.halo.description = "Зеркало </script><script>alert(1)</script>"
    shop.halo.save()

    html = page_html(client, "/catalog/zerkala/halo-moon/")

    assert "</script><script>alert(1)" not in html
    assert block_of(html, "Product")["description"].startswith("Зеркало")


# --- Canonical -------------------------------------------------------


def canonical_of(html: str) -> str:
    match = re.search(r'<link rel="canonical" href="([^"]*)"', html)
    assert match
    return match.group(1)


def test_filtered_url_canonicalizes_to_category(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/?podsvetka=1")

    assert canonical_of(html).endswith("/catalog/zerkala/")


def test_sorted_url_canonicalizes_to_category(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/?sort=price")

    assert canonical_of(html).endswith("/catalog/zerkala/")


def test_static_page_is_self_canonical(
    client: Client, shop: SimpleNamespace
) -> None:
    assert canonical_of(page_html(client, "/about/")).endswith("/about/")


def fill_page_two(shop: SimpleNamespace) -> None:
    """Товаров ровно на вторую страницу выдачи."""
    for number in range(PAGE_SIZE):
        product = Product.objects.create(
            category=shop.category,
            name=f"Зеркало {number}",
            slug=f"zerkalo-{number}",
            price=5000 + number,
            is_published=True,
        )
        ProductAttribute.objects.create(
            product=product, attribute=shop.podsvetka, value_bool=True
        )


def test_category_pagination_is_self_canonical(
    client: Client, shop: SimpleNamespace
) -> None:
    fill_page_two(shop)

    html = page_html(client, "/catalog/zerkala/?page=2")

    assert canonical_of(html).endswith("/catalog/zerkala/?page=2")


def test_landing_pagination_is_self_canonical(
    client: Client, shop: SimpleNamespace
) -> None:
    fill_page_two(shop)

    html = page_html(client, "/zerkala-s-podsvetkoy/?page=2")

    assert canonical_of(html).endswith("/zerkala-s-podsvetkoy/?page=2")


# --- Посадочные ------------------------------------------------------


def test_landing_shows_only_matching_products(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/zerkala-s-podsvetkoy/")

    assert "Halo Moon" in html
    assert "View Match" not in html


def test_landing_uses_its_own_title_heading_and_text(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/zerkala-s-podsvetkoy/")

    assert "<title>Зеркала с подсветкой на заказ — memiro</title>" in html
    assert '<h1 class="h-section">Зеркала с подсветкой</h1>' in html
    assert "Подсветка по контуру не слепит" in html
    assert meta_content(html, "description").startswith(
        "Зеркала с подсветкой на заказ"
    )


def test_landing_is_indexable_and_self_canonical(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/zerkala-s-podsvetkoy/")

    assert canonical_of(html).endswith("/zerkala-s-podsvetkoy/")
    assert 'name="robots"' not in html


def test_unpublished_landing_is_hidden(
    client: Client, shop: SimpleNamespace
) -> None:
    shop.landing.is_published = False
    shop.landing.save()

    response = client.get("/zerkala-s-podsvetkoy/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_landing_without_products_is_404(
    client: Client, shop: SimpleNamespace
) -> None:
    """Пустая посадочная — такая же пустая комбинация, как у фильтров."""
    Product.objects.filter(pk=shop.halo.pk).update(is_published=False)

    response = client.get("/zerkala-s-podsvetkoy/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_category_links_to_its_landings(
    client: Client, shop: SimpleNamespace
) -> None:
    html = page_html(client, "/catalog/zerkala/")

    assert 'href="/zerkala-s-podsvetkoy/"' in html


def test_category_hides_link_to_empty_landing(
    client: Client, shop: SimpleNamespace
) -> None:
    """Посадочная без товаров отдаёт 404 — ссылки на неё быть не должно."""
    Product.objects.filter(pk=shop.halo.pk).update(is_published=False)

    html = page_html(client, "/catalog/zerkala/")

    assert "/zerkala-s-podsvetkoy/" not in html


def test_landing_slug_cannot_shadow_existing_page(
    shop: SimpleNamespace,
) -> None:
    landing = Landing(
        category=shop.category,
        slug="about",
        title="t",
        heading="h",
        description="d",
    )

    with pytest.raises(ValidationError) as error:
        landing.full_clean()

    assert "slug" in error.value.message_dict


def test_landing_condition_rejects_foreign_attribute(
    shop: SimpleNamespace,
) -> None:
    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    foreign = Attribute.objects.create(
        category=other,
        name="Стекло",
        slug="steklo",
        kind=Attribute.Kind.BOOLEAN,
    )

    condition = LandingCondition(
        landing=shop.landing, attribute=foreign, value_bool=True
    )

    with pytest.raises(ValidationError) as error:
        condition.full_clean()

    assert "attribute" in error.value.message_dict


# --- sitemap.xml и robots.txt ----------------------------------------


def test_sitemap_lists_published_pages(
    client: Client, shop: SimpleNamespace
) -> None:
    Product.objects.create(
        category=shop.category, name="Черновик", slug="draft", price=1000
    )

    response = client.get("/sitemap.xml")
    xml = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    for path in (
        "/catalog/zerkala/",
        "/catalog/zerkala/halo-moon/",
        "/zerkala-s-podsvetkoy/",
        "/about/",
        "/works/",
    ):
        assert path in xml
    assert "/catalog/zerkala/draft/" not in xml


def test_sitemap_skips_redirecting_catalog_root(
    client: Client, shop: SimpleNamespace
) -> None:
    """С единственной категорией /catalog/ отвечает редиректом."""
    xml = client.get("/sitemap.xml").content.decode()

    assert "<loc>http://testserver/catalog/</loc>" not in xml

    other = Category.objects.create(name="Перегородки", slug="peregorodki")
    Product.objects.create(
        category=other,
        name="Перегородка",
        slug="peregorodka",
        price=30000,
        is_published=True,
    )

    xml = client.get("/sitemap.xml").content.decode()

    assert "<loc>http://testserver/catalog/</loc>" in xml


def test_sitemap_hides_unpublished_landing(
    client: Client, shop: SimpleNamespace
) -> None:
    shop.landing.is_published = False
    shop.landing.save()

    xml = client.get("/sitemap.xml").content.decode()

    assert "/zerkala-s-podsvetkoy/" not in xml


def test_sitemap_hides_landing_without_products(
    client: Client, shop: SimpleNamespace
) -> None:
    """Посадочная без товаров отдаёт 404 — в карте ей не место."""
    Product.objects.filter(pk=shop.halo.pk).update(is_published=False)

    xml = client.get("/sitemap.xml").content.decode()

    assert "/zerkala-s-podsvetkoy/" not in xml


def test_robots_closes_filter_params_and_points_to_sitemap(
    client: Client, shop: SimpleNamespace
) -> None:
    response = client.get("/robots.txt")
    text = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert response.headers["Content-Type"].startswith("text/plain")
    assert "Disallow: /admin/" in text
    assert "Disallow: /*?*podsvetka=" in text
    assert "Disallow: /*?*sort=" in text
    # Цена — такой же параметрический дубль (тикет 13)
    assert "Disallow: /*?*price_min=" in text
    assert "Disallow: /*?*price_max=" in text
    # Clean-param — то же самое для Яндекса
    clean = next(
        line for line in text.splitlines() if line.startswith("Clean-param:")
    )
    assert "podsvetka" in clean
    assert "forma" in clean
    assert "sort" in clean
    assert "price_min" in clean
    assert "price_max" in clean
    assert "Sitemap: http://testserver/sitemap.xml" in text


# --- Переезд домена --------------------------------------------------


def test_old_product_url_redirects_permanently(
    client: Client, shop: SimpleNamespace
) -> None:
    LegacyUrl.objects.create(
        old_path="/mirrors/halo-moon/",
        new_path="/catalog/zerkala/halo-moon/",
    )

    response = client.get("/mirrors/halo-moon/")

    assert response.status_code == HTTPStatus.MOVED_PERMANENTLY
    assert response.headers["Location"] == "/catalog/zerkala/halo-moon/"


def test_old_article_is_gone(client: Client, shop: SimpleNamespace) -> None:
    LegacyUrl.objects.create(old_path="/2023/01/statya/")

    response = client.get("/2023/01/statya/")

    assert response.status_code == HTTPStatus.GONE


def test_unknown_url_stays_404(client: Client, shop: SimpleNamespace) -> None:
    assert client.get("/net-takogo/").status_code == HTTPStatus.NOT_FOUND


def test_import_legacy_urls_loads_map(db: None, tmp_path: object) -> None:
    source = tmp_path / "map.json"  # type: ignore[operator]
    source.write_text(
        json.dumps(
            {
                "redirects": {
                    "mirrors/halo-moon": "catalog/zerkala/halo-moon"
                },
                "gone": ["/2023/01/statya/"],
            }
        ),
        encoding="utf-8",
    )

    call_command("import_legacy_urls", str(source))

    redirect = LegacyUrl.objects.get(old_path="/mirrors/halo-moon/")
    assert redirect.new_path == "/catalog/zerkala/halo-moon/"
    assert LegacyUrl.objects.get(old_path="/2023/01/statya/").is_gone
