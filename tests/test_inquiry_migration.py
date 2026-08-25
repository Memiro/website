"""Переезд конфигурации на позицию заявки не теряет принятых заявок.

Тест гоняет саму миграцию, а не её функции с живым реестром моделей:
у нынешней `Inquiry` полей уже нет, и вызвать перенос по ней нельзя —
как раз это он и проверяет (тикет 14, ADR-0009).
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.db.migrations.state import StateApps
    from django.db.models import Model

# Имя модуля миграции начинается с цифры — обычным import не взять
moving = import_module(
    "memiro.inquiries.migrations.0005_configuration_per_item"
)

BEFORE = ("inquiries", "0004_inquiry_calculated_price_inquiry_configuration")
AFTER = ("inquiries", "0005_configuration_per_item")

CONFIGURATION = "800 × 600 мм; Тип полотна: Серебро"
PRICE = 5500


def migrate(target: tuple[str, str]) -> StateApps:
    """Довести базу до состояния миграции и отдать её модели."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate([target])
    return executor.loader.project_state([target]).apps


@pytest.fixture
def at_the_old_state() -> Iterator[StateApps]:
    """База на миграции до переезда; после теста — снова на последней."""
    try:
        yield migrate(BEFORE)
    finally:
        # Иначе следующий тест получил бы базу без полей позиции.
        # Тест мог не дойти до отката сам — потому finally, а не хвост
        migrate(AFTER)


def inquiry(apps: StateApps, **overrides: object) -> Model:
    """Принятая заявка со снимком расчёта — какой её знала модель до."""
    fields = {
        "name": "Анна",
        "phone": "+7 981 000-00-00",
        "consent": True,
        "source": "product",
        "configuration": CONFIGURATION,
        "calculated_price": PRICE,
    } | overrides
    created: Model = apps.get_model("inquiries", "Inquiry").objects.create(
        **fields
    )
    return created


def add_item(apps: StateApps, parent: Model, name: str) -> Model:
    created: Model = apps.get_model("inquiries", "InquiryItem").objects.create(
        inquiry=parent, product_name=name, product_price=11795
    )
    return created


@pytest.mark.django_db(transaction=True)
def test_the_snapshot_moves_to_the_only_item(
    at_the_old_state: StateApps,
) -> None:
    """Заявке об одном зеркале снимок достаётся её единственной позиции."""
    old = inquiry(at_the_old_state)
    add_item(at_the_old_state, old, "Halo Moon")

    new = migrate(AFTER)

    stored = new.get_model("inquiries", "InquiryItem").objects.get()
    assert stored.configuration == CONFIGURATION
    assert stored.calculated_price == PRICE


@pytest.mark.django_db(transaction=True)
def test_a_free_form_inquiry_passes_untouched(
    at_the_old_state: StateApps,
) -> None:
    """Заявке свободной формой снимок отдавать некому — и нечему.

    Позиции у неё нет вовсе, снимка тоже, и миграция проходит мимо,
    а не падает.
    """
    inquiry(
        at_the_old_state,
        source="home",
        configuration="",
        calculated_price=None,
        comment="Перезвоните после шести",
    )

    new = migrate(AFTER)

    assert not new.get_model("inquiries", "InquiryItem").objects.exists()
    stored = new.get_model("inquiries", "Inquiry").objects.get()
    assert stored.comment == "Перезвоните после шести"


@pytest.mark.django_db(transaction=True)
def test_a_snapshot_without_any_item_moves_to_the_comment(
    at_the_old_state: StateApps,
) -> None:
    """Позиции у снимка нет — но и терять его нельзя (тикет 14).

    Так до тикета 07 приходил расчёт с карточки: старый разбор писал
    в снимок габариты, даже не найдя единственного товара. Позиции
    такому снимку не создать — зеркало в ней было бы выдуманным, —
    и он уходит в комментарий, где его не примут за конфигурацию.
    """
    inquiry(at_the_old_state, comment="Нужен замер")

    new = migrate(AFTER)

    stored = new.get_model("inquiries", "Inquiry").objects.get()
    assert stored.comment.startswith("Нужен замер")
    assert moving.KEPT_IN_COMMENT in stored.comment
    assert CONFIGURATION in stored.comment
    assert f"{PRICE} ₽" in stored.comment


@pytest.mark.django_db(transaction=True)
def test_a_kept_snapshot_says_when_there_was_no_price(
    at_the_old_state: StateApps,
) -> None:
    """Цены у снимка могло не быть — и это пишется словами."""
    inquiry(at_the_old_state, calculated_price=None)

    new = migrate(AFTER)

    stored = new.get_model("inquiries", "Inquiry").objects.get()
    assert "цена не рассчитана" in stored.comment


@pytest.mark.django_db(transaction=True)
def test_a_snapshot_is_not_guessed_onto_one_of_many_items(
    at_the_old_state: StateApps,
) -> None:
    """Какое из зеркал покупатель считал, знает только он.

    Раздать один снимок нескольким позициям — сказать менеджеру
    неправду о двух из них; угаданная конфигурация хуже отсутствующей.
    """
    old = inquiry(at_the_old_state)
    add_item(at_the_old_state, old, "Halo Moon")
    add_item(at_the_old_state, old, "View Match")

    new = migrate(AFTER)

    items = new.get_model("inquiries", "InquiryItem").objects.all()
    assert [stored.configuration for stored in items] == ["", ""]
    # Но и не потерян: раздать его некому, забыть — нельзя
    assert (
        CONFIGURATION
        in new.get_model("inquiries", "Inquiry").objects.get().comment
    )


@pytest.mark.django_db(transaction=True)
def test_the_snapshot_comes_back_to_the_inquiry_on_rollback(
    at_the_old_state: StateApps,
) -> None:
    """Откат дорогой, и потому проверен: снимок возвращается заявке.

    ADR-0009 зовёт это решение дорогим в откате — тем важнее, чтобы
    откат отрабатывал, а не падал на первой же настроенной позиции.
    """
    old = inquiry(at_the_old_state, configuration="", calculated_price=None)
    add_item(at_the_old_state, old, "Halo Moon")
    new = migrate(AFTER)
    stored = new.get_model("inquiries", "InquiryItem").objects.get()
    stored.configuration = CONFIGURATION
    stored.calculated_price = PRICE
    stored.save()

    back = migrate(BEFORE)

    returned = back.get_model("inquiries", "Inquiry").objects.get()
    assert returned.configuration == CONFIGURATION
    assert returned.calculated_price == PRICE


@pytest.mark.django_db(transaction=True)
def test_the_rollback_returns_the_first_configured_position(
    at_the_old_state: StateApps,
) -> None:
    """Двум конфигурациям в старой модели места нет — берётся первая.

    Она первая по `pk`: `InquiryItem` так и упорядочен, и откат не
    зависит от того, в каком порядке база вернула строки.
    """
    old = inquiry(at_the_old_state, configuration="", calculated_price=None)
    add_item(at_the_old_state, old, "Halo Moon")
    add_item(at_the_old_state, old, "View Match")
    new = migrate(AFTER)
    positions = new.get_model("inquiries", "InquiryItem").objects.order_by(
        "pk"
    )
    for position, label in zip(
        positions, (CONFIGURATION, "1200 × 400 мм"), strict=True
    ):
        position.configuration = label
        position.save()

    back = migrate(BEFORE)

    assert (
        back.get_model("inquiries", "Inquiry").objects.get().configuration
        == CONFIGURATION
    )
