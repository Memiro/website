"""Фильтры каталога поверх атрибутов категории (CONTEXT.md, ADR-0002).

Значения одного атрибута объединяются по ИЛИ, разные атрибуты — по И.
Фильтры строятся из атрибутов типов «выбор из списка» и «да/нет»;
числовые атрибуты выводятся в карточке товара, но фильтров не дают.
Счётчик значения — количество товаров при всех остальных выбранных
фильтрах, кроме фильтров своего атрибута (UX-практика Baymard).

Цена — единственное сужение не из атрибутов, а из поля товара, и
группой она не является: выбранный диапазон учитывается в счётчиках
всех групп, включая ту, значение которой сейчас считается.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Count, Max, Min

from .formatting import rub
from .models import (
    BOOL_LABELS,
    BOOL_TOKENS,
    Attribute,
    AttributeValue,
    ProductAttribute,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import QueryDict

    from .models import Category, Product


class FilterError(Exception):
    """Мусорное значение фильтра в querystring — такой страницы нет."""


FILTERABLE_KINDS = (Attribute.Kind.CHOICE, Attribute.Kind.BOOLEAN)

PRICE_MIN_PARAM = "price_min"
PRICE_MAX_PARAM = "price_max"
# Параметры цены закрываются от индексации наравне с прочими (ADR-0003)
PRICE_PARAMS = (PRICE_MIN_PARAM, PRICE_MAX_PARAM)


@dataclass(frozen=True)
class FilterOption:
    """Одна строка-чекбокс в группе фильтра."""

    label: str
    token: str
    count: int
    is_selected: bool


@dataclass(frozen=True)
class FilterGroup:
    """Группа фильтра — один атрибут категории со своими значениями."""

    attribute: Attribute
    options: tuple[FilterOption, ...]


@dataclass(frozen=True)
class AppliedFilter:
    """Применённое значение для чипса с крестиком.

    `param` — имя параметра в querystring: у атрибута это его слаг,
    у цены — `price_min`/`price_max`.
    """

    label: str
    param: str
    token: str


@dataclass(frozen=True)
class PriceRange:
    """Границы цены, выбранные посетителем; None — граница не задана."""

    minimum: int | None = None
    maximum: int | None = None

    @classmethod
    def parse(cls, query: QueryDict) -> PriceRange:
        """Разбирает границы из querystring; мусор — FilterError."""
        return cls(
            minimum=cls._parse_bound(query, PRICE_MIN_PARAM),
            maximum=cls._parse_bound(query, PRICE_MAX_PARAM),
        )

    @staticmethod
    def _parse_bound(query: QueryDict, param: str) -> int | None:
        """Одно каноничное число — иначе страницы нет.

        Строгость тут не придирчивость: крестик чипа снимает границу,
        сравнивая своё значение со строкой в querystring, и `08352`
        или второй такой же параметр дали бы чип, который не снимается.
        """
        values = query.getlist(param)
        if not values or values == [""]:
            return None
        raw = values[0]
        if len(values) > 1:
            message = f"Граница «{param}» задана дважды"
            raise FilterError(message)
        # Не int(): тот принял бы «1_000», «+900» и арабские цифры
        if not (raw.isascii() and raw.isdigit()) or str(int(raw)) != raw:
            message = f"Цена «{raw}» не число"
            raise FilterError(message)
        return int(raw)

    @property
    def is_active(self) -> bool:
        return self.minimum is not None or self.maximum is not None

    def apply(self, products: QuerySet[Product]) -> QuerySet[Product]:
        """Сужает выборку по цене; границы включаются в диапазон."""
        if self.minimum is not None:
            products = products.filter(price__gte=self.minimum)
        if self.maximum is not None:
            products = products.filter(price__lte=self.maximum)
        return products

    def chips(self) -> list[AppliedFilter]:
        """Границы — отдельные чипсы: каждая снимается сама по себе."""
        bounds = (
            ("от", PRICE_MIN_PARAM, self.minimum),
            ("до", PRICE_MAX_PARAM, self.maximum),
        )
        return [
            AppliedFilter(
                label=f"Цена {preposition} {rub(value)} ₽",
                param=param,
                token=str(value),
            )
            for preposition, param, value in bounds
            if value is not None
        ]


@dataclass(frozen=True)
class PriceControl:
    """Пара полей «от» и «до» в сайдбаре.

    Границы считаются из опубликованных товаров категории, а не зашиты
    в вёрстку: у каждой категории свой разброс, и он меняется вместе
    с каталогом.
    """

    lowest: int
    highest: int
    selected: PriceRange

    @classmethod
    def build(
        cls, products: QuerySet[Product], selected: PriceRange
    ) -> PriceControl | None:
        """Границы по опубликованным товарам категории.

        None — сужать нечем: все товары категории стоят одинаково.
        """
        bounds = products.aggregate(low=Min("price"), high=Max("price"))
        low, high = bounds["low"], bounds["high"]
        if low is None or low == high:
            return None
        return cls(lowest=low, highest=high, selected=selected)


class CatalogFilters:
    """Разобранный набор фильтров одной категории."""

    def __init__(
        self,
        attributes: list[Attribute],
        choice_selected: dict[Attribute, tuple[AttributeValue, ...]],
        bool_selected: dict[Attribute, tuple[bool, ...]],
        price: PriceRange | None = None,
    ) -> None:
        self._attributes = attributes
        self._choice = choice_selected
        self._bool = bool_selected
        self._price = price or PriceRange()

    @classmethod
    def parse(cls, category: Category, query: QueryDict) -> CatalogFilters:
        """Собирает выбор из querystring; мусор — FilterError.

        Параметры, не совпадающие со слагами атрибутов категории
        (page, sort, utm и прочие), игнорируются.
        """
        attributes = list(
            category.attributes.filter(
                kind__in=FILTERABLE_KINDS
            ).prefetch_related("values")
        )
        choice_selected: dict[Attribute, tuple[AttributeValue, ...]] = {}
        bool_selected: dict[Attribute, tuple[bool, ...]] = {}
        for attribute in attributes:
            tokens = query.getlist(attribute.slug)
            if not tokens:
                continue
            if attribute.kind == Attribute.Kind.CHOICE:
                choice_selected[attribute] = cls._parse_choice(
                    attribute, tokens
                )
            else:
                bool_selected[attribute] = cls._parse_bool(attribute, tokens)
        return cls(
            attributes,
            choice_selected,
            bool_selected,
            PriceRange.parse(query),
        )

    @staticmethod
    def _parse_choice(
        attribute: Attribute, tokens: list[str]
    ) -> tuple[AttributeValue, ...]:
        by_token = {str(value.pk): value for value in attribute.values.all()}
        try:
            return tuple(by_token[token] for token in tokens)
        except KeyError as error:
            message = f"Нет значения {error} у атрибута «{attribute}»"
            raise FilterError(message) from error

    @staticmethod
    def _parse_bool(
        attribute: Attribute, tokens: list[str]
    ) -> tuple[bool, ...]:
        try:
            return tuple(BOOL_TOKENS[token] for token in tokens)
        except KeyError as error:
            message = f"Нет значения {error} у атрибута «{attribute}»"
            raise FilterError(message) from error

    @property
    def is_active(self) -> bool:
        return bool(self._choice or self._bool) or self._price.is_active

    def apply(
        self,
        products: QuerySet[Product],
        *,
        exclude: Attribute | None = None,
    ) -> QuerySet[Product]:
        """Сужает выборку: ИЛИ внутри атрибута, И между атрибутами.

        `exclude` снимает одну группу — цены это не касается: группой
        она не является и из счётчиков не выпадает.
        """
        products = self._price.apply(products)
        for attribute, values in self._choice.items():
            if attribute == exclude:
                continue
            products = products.filter(
                attribute_values__attribute=attribute,
                attribute_values__value_option__in=values,
            )
        for attribute, flags in self._bool.items():
            if attribute == exclude:
                continue
            products = products.filter(
                attribute_values__attribute=attribute,
                attribute_values__value_bool__in=flags,
            )
        return products

    def groups(self, base: QuerySet[Product]) -> list[FilterGroup]:
        """Группы для сайдбара со счётчиками значений.

        `base` — все опубликованные товары категории, без фильтров.
        """
        return [
            FilterGroup(
                attribute=attribute,
                options=self._options(attribute, base),
            )
            for attribute in self._attributes
        ]

    def price_control(self, base: QuerySet[Product]) -> PriceControl | None:
        """Поля «от» и «до» для сайдбара — рядом с группами атрибутов."""
        return PriceControl.build(base, self._price)

    def _options(
        self, attribute: Attribute, base: QuerySet[Product]
    ) -> tuple[FilterOption, ...]:
        subset = self.apply(base, exclude=attribute)
        if attribute.kind == Attribute.Kind.CHOICE:
            return self._choice_options(attribute, subset)
        return self._bool_options(attribute, subset)

    def _choice_options(
        self, attribute: Attribute, subset: QuerySet[Product]
    ) -> tuple[FilterOption, ...]:
        counts = dict(
            ProductAttribute.objects.filter(
                attribute=attribute, product__in=subset
            )
            .values("value_option")
            .annotate(n=Count("id"))
            .values_list("value_option", "n")
        )
        selected = {value.pk for value in self._choice.get(attribute, ())}
        return tuple(
            FilterOption(
                label=value.value,
                token=str(value.pk),
                count=counts.get(value.pk, 0),
                is_selected=value.pk in selected,
            )
            for value in attribute.values.all()
        )

    def _bool_options(
        self, attribute: Attribute, subset: QuerySet[Product]
    ) -> tuple[FilterOption, ...]:
        counts = dict(
            ProductAttribute.objects.filter(
                attribute=attribute, product__in=subset
            )
            .values("value_bool")
            .annotate(n=Count("id"))
            .values_list("value_bool", "n")
        )
        selected = set(self._bool.get(attribute, ()))
        return tuple(
            FilterOption(
                label=BOOL_LABELS[flag],
                token=token,
                count=counts.get(flag, 0),
                is_selected=flag in selected,
            )
            for token, flag in BOOL_TOKENS.items()
        )

    def applied(self) -> list[AppliedFilter]:
        """Применённые значения в порядке атрибутов — для чипсов."""
        chips: list[AppliedFilter] = []
        for attribute in self._attributes:
            chips.extend(
                AppliedFilter(
                    label=f"{attribute.name}: {value.value}",
                    param=attribute.slug,
                    token=str(value.pk),
                )
                for value in self._choice.get(attribute, ())
            )
            chips.extend(
                AppliedFilter(
                    label=f"{attribute.name}: {BOOL_LABELS[flag]}",
                    param=attribute.slug,
                    token="1" if flag else "0",
                )
                for flag in self._bool.get(attribute, ())
            )
        chips.extend(self._price.chips())
        return chips
