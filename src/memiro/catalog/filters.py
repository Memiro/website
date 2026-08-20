"""Фильтры каталога поверх атрибутов категории (CONTEXT.md, ADR-0002).

Значения одного атрибута объединяются по ИЛИ, разные атрибуты — по И.
Фильтры строятся из атрибутов типов «выбор из списка» и «да/нет»;
числовые атрибуты выводятся в карточке товара, но фильтров не дают.
Счётчик значения — количество товаров при всех остальных выбранных
фильтрах, кроме фильтров своего атрибута (UX-практика Baymard).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Count

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
    """Применённое значение для чипса с крестиком."""

    label: str
    slug: str
    token: str


class CatalogFilters:
    """Разобранный набор фильтров одной категории."""

    def __init__(
        self,
        attributes: list[Attribute],
        choice_selected: dict[Attribute, tuple[AttributeValue, ...]],
        bool_selected: dict[Attribute, tuple[bool, ...]],
    ) -> None:
        self._attributes = attributes
        self._choice = choice_selected
        self._bool = bool_selected

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
        return cls(attributes, choice_selected, bool_selected)

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
        return bool(self._choice or self._bool)

    def apply(
        self,
        products: QuerySet[Product],
        *,
        exclude: Attribute | None = None,
    ) -> QuerySet[Product]:
        """Сужает выборку: ИЛИ внутри атрибута, И между атрибутами."""
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
                    slug=attribute.slug,
                    token=str(value.pk),
                )
                for value in self._choice.get(attribute, ())
            )
            chips.extend(
                AppliedFilter(
                    label=f"{attribute.name}: {BOOL_LABELS[flag]}",
                    slug=attribute.slug,
                    token="1" if flag else "0",
                )
                for flag in self._bool.get(attribute, ())
            )
        return chips
