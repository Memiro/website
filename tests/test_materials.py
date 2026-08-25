"""Экран «Материалы и цены» (тикет 17).

Экран не заводит своей цены — он показывает поперёк атрибутов те же
строки справочника, у которых цена и живёт (ADR-0007). Поэтому
проверяется не устройство админки, а поведение: что оказалось в
списке, что стало с ценами после правки тарифа, что сказали правила
справочника и что владелец об этом прочитал.
"""

from __future__ import annotations

from decimal import Decimal
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from django.test import Client

from memiro.catalog.models import (
    Attribute,
    AttributeValue,
    Category,
    Product,
    ProductVariant,
)

SCREEN = "/admin/catalog/materialprice/"

# Серебро 4 000 ₽/м², 800 × 600 — 0,48 м²; итог округляется вверх
# до сотни рублей
SILVER_800_600 = 2000
SILVER_AFTER_RAISE = 2900


@pytest.fixture
def dictionary(db: None) -> SimpleNamespace:
    """Справочник зеркал: платное полотно, бесплатная рама, вырез.

    «Графит» без тарифа — из тех 425 значений, что переехали со
    старого сайта до заведения цен.
    """
    category = Category.objects.create(name="Зеркала", slug="zerkala")
    blade = Attribute.objects.create(
        category=category, name="Тип полотна", slug="tip-polotna"
    )
    silver = AttributeValue.objects.create(
        attribute=blade,
        value="Серебро",
        unit=AttributeValue.Unit.SQUARE_METER,
        rate=Decimal(4000),
        scaled_by_shape=True,
    )
    graphite = AttributeValue.objects.create(
        attribute=blade, value="Графит", order=1
    )
    illumination = Attribute.objects.create(
        category=category, name="Подсветка", slug="podsvetka", order=1
    )
    contour = AttributeValue.objects.create(
        attribute=illumination,
        value="Контурная",
        unit=AttributeValue.Unit.LINEAR_METER,
        rate=Decimal(2500),
    )
    frame = Attribute.objects.create(
        category=category, name="Рама", slug="rama", order=2
    )
    without_frame = AttributeValue.objects.create(
        attribute=frame, value="Без рамы", marks_absence=True
    )
    product = Product.objects.create(
        category=category, name="Halo Moon", slug="halo-moon"
    )
    variant = ProductVariant.objects.create(
        product=product, width_mm=800, height_mm=600
    )
    variant.values.add(silver)
    return SimpleNamespace(
        category=category,
        blade=blade,
        silver=silver,
        graphite=graphite,
        contour=contour,
        without_frame=without_frame,
        product=product,
        variant=variant,
    )


def edit(
    client: Client,
    value: AttributeValue,
    *,
    unit: str,
    rate: str,
    scaled_by_shape: bool = False,
) -> str:
    """Правка строки прямо в списке — как её шлёт браузер.

    Снятый флажок браузер не шлёт вовсе, поэтому и здесь его нет:
    пачечная правка тем и опасна, что молча меняет то, о чём владелец
    не думал, — и проверять это надо на том, что уходит на сервер.
    """
    payload = {
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "1",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-id": str(value.pk),
        "form-0-unit": unit,
        "form-0-rate": rate,
        "_save": "",
    }
    if scaled_by_shape:
        payload["form-0-scaled_by_shape"] = "on"
    response = client.post(SCREEN, payload, follow=True)

    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


def screen(client: Client, query: str = "") -> str:
    response = client.get(SCREEN + query)

    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


# --- что видно в списке -----------------------------------------------


def test_screen_shows_prices_of_every_attribute_at_once(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Ради этого экран и заведён: цены лежали по разным атрибутам."""
    html = screen(admin_client)

    assert "Серебро" in html
    assert "Тип полотна" in html
    assert "Контурная" in html
    assert "Подсветка" in html


def test_screen_leaves_out_what_cannot_cost_money(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Отсутствие признака тарифа не несёт и по правилу не понесёт."""
    html = screen(admin_client)

    assert "Без рамы" not in html


def test_values_without_a_tariff_are_findable(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """«Бесплатно» от «руки не дошли» владелец отличает глазами."""
    html = screen(admin_client, "?unit=none")

    assert "Графит" in html
    assert "Серебро" not in html


def test_search_finds_a_value_by_its_name(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    html = screen(admin_client, "?q=Графит")

    assert "Графит" in html
    assert "Серебро" not in html


def test_screen_filters_by_attribute(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Экран плоский, и в нём вперемешку значения всех атрибутов."""
    html = screen(admin_client, f"?attribute__id__exact={dictionary.blade.pk}")

    assert "Серебро" in html
    assert "Контурная" not in html


# --- правка тарифа ----------------------------------------------------


def test_a_rate_edited_in_the_list_reaches_the_prices(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Ради этого владелец сюда и приходит: цены пересчитались."""
    dictionary.variant.refresh_from_db()
    assert dictionary.variant.price == SILVER_800_600

    edit(
        admin_client,
        dictionary.silver,
        unit=AttributeValue.Unit.SQUARE_METER,
        rate="6000",
        scaled_by_shape=True,
    )

    dictionary.variant.refresh_from_db()
    dictionary.product.refresh_from_db()
    assert dictionary.variant.price == SILVER_AFTER_RAISE
    assert dictionary.product.price == SILVER_AFTER_RAISE


def test_the_owner_reads_that_the_prices_were_repriced(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Пересчёт молчалив, и владелец уходил бы проверять руками."""
    html = edit(
        admin_client,
        dictionary.silver,
        unit=AttributeValue.Unit.SQUARE_METER,
        rate="6000",
        scaled_by_shape=True,
    )

    assert "Цены пересчитаны" in html


def test_a_tariff_is_given_a_new_unit_right_in_the_list(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Значение без тарифа тариф здесь и получает."""
    edit(
        admin_client,
        dictionary.graphite,
        unit=AttributeValue.Unit.PIECE,
        rate="900",
    )

    dictionary.graphite.refresh_from_db()
    assert dictionary.graphite.unit == AttributeValue.Unit.PIECE
    assert dictionary.graphite.rate == Decimal(900)


def test_the_shape_factor_flag_is_set_right_in_the_list(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Признак — часть тарифа: контурная лента и полотно меряются
    одним погонным метром, а на криволинейном резе дорожает полотно.
    """
    edit(
        admin_client,
        dictionary.graphite,
        unit=AttributeValue.Unit.SQUARE_METER,
        rate="5000",
        scaled_by_shape=True,
    )

    dictionary.graphite.refresh_from_db()
    assert dictionary.graphite.scaled_by_shape


def test_a_batch_of_rows_is_repriced_and_told_about_once(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Пачкой правят по два десятка строк — сообщение одно на всю.

    Двадцать одинаковых сообщений о пересчёте перестают читать.
    """
    response = admin_client.post(
        SCREEN,
        {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(dictionary.silver.pk),
            "form-0-unit": AttributeValue.Unit.SQUARE_METER,
            "form-0-rate": "6000",
            "form-0-scaled_by_shape": "on",
            "form-1-id": str(dictionary.contour.pk),
            "form-1-unit": AttributeValue.Unit.LINEAR_METER,
            "form-1-rate": "3000",
            "_save": "",
        },
        follow=True,
    )

    assert response.status_code == HTTPStatus.OK
    dictionary.silver.refresh_from_db()
    dictionary.contour.refresh_from_db()
    dictionary.variant.refresh_from_db()
    assert dictionary.silver.rate == Decimal(6000)
    assert dictionary.contour.rate == Decimal(3000)
    assert dictionary.variant.price == SILVER_AFTER_RAISE
    assert response.content.decode().count("Цены пересчитаны") == 1


def test_the_edit_stays_in_the_history_of_the_screen(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Иначе история правки цен лежала бы мимо экрана, где её ищут."""
    edit(
        admin_client,
        dictionary.silver,
        unit=AttributeValue.Unit.SQUARE_METER,
        rate="6000",
        scaled_by_shape=True,
    )

    response = admin_client.get(f"{SCREEN}{dictionary.silver.pk}/history/")

    assert response.status_code == HTTPStatus.OK
    assert "тариф" in response.content.decode().lower()


# --- правила справочника ----------------------------------------------


def test_half_a_tariff_is_refused(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Ставка без единицы расхода молча считалась бы нулём."""
    html = edit(admin_client, dictionary.graphite, unit="", rate="900")

    dictionary.graphite.refresh_from_db()
    assert dictionary.graphite.rate is None
    assert "Укажите единицу расхода" in html


def test_the_shape_factor_is_refused_to_a_free_value(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """У бесплатного значения нет статьи, которую можно умножить."""
    html = edit(
        admin_client,
        dictionary.graphite,
        unit="",
        rate="",
        scaled_by_shape=True,
    )

    dictionary.graphite.refresh_from_db()
    assert not dictionary.graphite.scaled_by_shape
    assert "Коэффициент формы умножает статью расхода" in html


def test_a_rule_about_a_column_outside_the_row_is_spoken_not_crashed(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Правило числового атрибута указывает на поле, которого в
    строке нет, — и Django отвечает на такое падением страницы.
    """
    cutout = Attribute.objects.create(
        category=dictionary.category,
        name="Вырез",
        slug="vyrez",
        kind=Attribute.Kind.NUMBER,
        order=2,
    )
    first = AttributeValue.objects.create(
        attribute=cutout,
        value="Вырез",
        unit=AttributeValue.Unit.PIECE,
        rate=Decimal(500),
    )
    AttributeValue.objects.create(attribute=cutout, value="Второй", order=1)

    html = edit(
        admin_client, first, unit=AttributeValue.Unit.PIECE, rate="700"
    )

    first.refresh_from_db()
    assert first.rate == Decimal(500)
    assert "строка справочника одна" in html


def test_a_single_row_opens_from_the_list(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Название значения в списке — ссылка, и вести ей есть куда."""
    response = admin_client.get(f"{SCREEN}{dictionary.silver.pk}/change/")

    assert response.status_code == HTTPStatus.OK
    html = response.content.decode()
    assert "Серебро" in html
    assert "Тип полотна" in html


# --- чего экран не делает ---------------------------------------------


def test_values_are_neither_born_nor_die_on_the_price_screen(
    admin_client: Client, dictionary: SimpleNamespace
) -> None:
    """Строка справочника — атрибут и значение; их здесь не спрашивают."""
    response = admin_client.get(SCREEN + "add/")

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "delete_selected" not in screen(admin_client)
