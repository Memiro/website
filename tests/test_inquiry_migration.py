"""Переезд конфигурации на позицию заявки не теряет принятых заявок.

Тест гоняет саму миграцию, а не её функции с живым реестром моделей:
у нынешней `Inquiry` полей уже нет, и вызвать перенос по ней нельзя —
как раз это он и проверяет (тикет 14, ADR-0009).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.db.migrations.state import StateApps
    from django.db.models import Model

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
def test_an_inquiry_without_items_loses_nothing(
    at_the_old_state: StateApps,
) -> None:
    """Заявке свободной формой снимок отдавать некому — и нечему.

    Позиции у неё нет вовсе, и миграция проходит мимо, а не падает.
    """
    inquiry(at_the_old_state, source="home", configuration="")

    new = migrate(AFTER)

    assert not new.get_model("inquiries", "InquiryItem").objects.exists()
    assert new.get_model("inquiries", "Inquiry").objects.count() == 1


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
