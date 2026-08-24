"""Когда цены вариантов и товаров пересчитываются заново.

Цена варианта — не то, что владелец вводит, а то, что движок считает
из справочника. Значит, у неё есть обязанность: доезжать до варианта
всякий раз, когда меняется хоть что-то из её слагаемых — сам вариант,
атрибуты его товара, тариф в справочнике или пороги расчёта. Иначе
таблица на карточке однажды разойдётся с калькулятором, и объяснить
расхождение покупателю будет нечем (тикет 17).

Цена товара — цена его самого дешёвого варианта, и держится она тем
же пересчётом: у неё те же слагаемые плюс появление и исчезновение
самих вариантов (тикет 18). Товар без единого варианта остаётся без
цены — NULL, а не заглушка.

Правка общих данных — тарифа в справочнике или порогов расчёта —
пересчитывает все варианты сразу. Выяснять, каких именно она
коснулась, дороже самого пересчёта: правят их в админке поштучно,
а сборка одной пачки укладывается в несколько запросов.

Запись идёт `update()`, а не `save()`: иначе пересчёт разбудил бы
сигнал, который его же и вызвал.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Min, OuterRef, Subquery
from django.db.models.signals import m2m_changed, post_delete, post_save

from . import tariffs
from .models import (
    AttributeValue,
    PricingSettings,
    Product,
    ProductAttribute,
    ProductVariant,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models import Model, QuerySet

# Изменения связи «многие ко многим», после которых состав уже новый
M2M_DONE = frozenset({"post_add", "post_remove", "post_clear"})


def reprice(variants: Iterable[ProductVariant]) -> None:
    """Считает цену каждого варианта пачки — и цену их товаров следом."""
    limits = tariffs.limits_from_settings()
    touched: set[int] = set()
    for variant in variants:
        total = tariffs.price(
            tariffs.configuration(
                variant.product,
                width_mm=variant.width_mm,
                height_mm=variant.height_mm,
                chosen=variant.values.all(),
            ),
            limits=limits,
        ).total
        if total != variant.price:
            ProductVariant.objects.filter(pk=variant.pk).update(price=total)
        variant.price = total
        touched.add(variant.product_id)
    settle_prices(touched)


def settle_prices(product_ids: Iterable[int]) -> None:
    """Ставит товарам цену их самого дешёвого варианта.

    Одним запросом на всю пачку — ради правки тарифа: она
    пересчитывает весь сайт, и подзапрос там дешевле восьмидесяти
    отдельных UPDATE. У товара без вариантов подзапрос пуст — цена
    становится NULL, и витрина о ней молчит.
    """
    ids = list(product_ids)
    if not ids:
        return
    Product.objects.filter(pk__in=ids).update(
        price=Subquery(
            ProductVariant.objects.filter(product_id=OuterRef("pk"))
            .values("product_id")
            .annotate(cheapest=Min("price"))
            .values("cheapest")
        )
    )


def all_variants() -> QuerySet[ProductVariant]:
    """Все варианты сайта, готовые к пересчёту без лишних запросов."""
    return (
        ProductVariant.objects.select_related("product")
        .prefetch_related("values__attribute")
        .prefetch_related(tariffs.product_values("product__"))
    )


def variants_of(product_id: int) -> QuerySet[ProductVariant]:
    """Варианты одного товара."""
    return all_variants().filter(product_id=product_id)


def _on_variant_saved(
    sender: type[Model],  # noqa: ARG001
    instance: ProductVariant,
    **kwargs: object,  # noqa: ARG001
) -> None:
    """Заведённый и поправленный вариант получает свою цену."""
    reprice([instance])


def _on_variant_deleted(
    sender: type[Model],  # noqa: ARG001
    instance: ProductVariant,
    **kwargs: object,  # noqa: ARG001
) -> None:
    """Удалённый вариант мог быть самым дешёвым — и единственным.

    Пересчитывать оставшиеся незачем: их слагаемые не менялись,
    поменялся только набор, из которого товар выбирает минимум.
    Поштучно — потому что варианты и удаляют поштучно, в карточке
    товара; пачками сюда приходит разве что каскад от самого товара,
    а ему цена уже без надобности.
    """
    settle_prices([instance.product_id])


def _on_variant_values_changed(
    sender: type[Model],  # noqa: ARG001
    instance: ProductVariant | AttributeValue,
    action: str,
    **kwargs: object,  # noqa: ARG001
) -> None:
    """Состав значений варианта меняют с обеих сторон связи.

    Со стороны значения справочника спросить, каких вариантов правка
    коснулась, уже нельзя: после `post_remove` и `post_clear` строк
    связи нет. Поэтому там пересчитываются все — как при правке
    тарифа, и по той же причине.
    """
    if action not in M2M_DONE:
        return
    if isinstance(instance, ProductVariant):
        reprice([instance])
        return
    reprice(all_variants())


def _on_product_attribute_changed(
    sender: type[Model],  # noqa: ARG001
    instance: ProductAttribute,
    **kwargs: object,  # noqa: ARG001
) -> None:
    """Атрибуты товара входят в цену каждого его варианта."""
    reprice(variants_of(instance.product_id))


def _on_shared_pricing_data_changed(
    sender: type[Model],  # noqa: ARG001
    instance: Model,  # noqa: ARG001
    **kwargs: object,  # noqa: ARG001
) -> None:
    """Тариф в справочнике и пороги расчёта общие для всех вариантов.

    Одной сущностью они не являются (CONTEXT.md, «Параметры расчёта»),
    но последствие правки у них одно.
    """
    reprice(all_variants())


def connect() -> None:
    """Подписывает пересчёт на всё, из чего складывается цена."""
    post_save.connect(_on_variant_saved, sender=ProductVariant)
    post_delete.connect(_on_variant_deleted, sender=ProductVariant)
    m2m_changed.connect(
        _on_variant_values_changed, sender=ProductVariant.values.through
    )
    for signal in (post_save, post_delete):
        signal.connect(_on_product_attribute_changed, sender=ProductAttribute)
        signal.connect(_on_shared_pricing_data_changed, sender=AttributeValue)
    post_save.connect(_on_shared_pricing_data_changed, sender=PricingSettings)
