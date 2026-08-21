"""Временно публикует товары в локальной SQLite ради визуального прогона.

База сохранена в db.sqlite3.bak и восстанавливается после скриншотов.
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memiro.settings")
django.setup()

from memiro.catalog.models import Product  # noqa: E402

count = Product.objects.update(is_published=True)
first = Product.objects.order_by("name").first()
print("published:", count)
print("sample:", first.slug, first.category.slug)
