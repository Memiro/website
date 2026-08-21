"""Фильтры шаблонов витрины — обёртки над `catalog.formatting`."""

from django import template

from memiro.catalog import formatting

register = template.Library()

register.filter("rub", formatting.rub)
register.filter("ru_plural", formatting.ru_plural)
