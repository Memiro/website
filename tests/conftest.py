"""Общие фикстуры тестов."""

from typing import TYPE_CHECKING

import pytest
from django.core.cache import cache

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _clear_throttling_cache() -> Iterator[None]:
    """Счётчики лимитов живут в кэше процесса — тесты не наследуют чужие."""
    cache.clear()
    yield
    cache.clear()
