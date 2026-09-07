"""The owner's wording for a domain refusal: the machine code is not a message (§12.4).

The flat table keyed by exact type is the admin's half of the mapping the API
keeps in ``error_handlers``; a miss is a code defect and is logged as one.
"""

from collections.abc import Iterator
from typing import Any

import structlog

from memiro.adapters.db.errors import LockTimeoutError
from memiro.application.errors.catalog import (
    AttributeInUseError,
    AttributeNotFoundError,
    AttributeValueInUseError,
    AttributeValueNotFoundError,
    CategoryNotFoundError,
    ProductImageNotFoundError,
    ProductNotFoundError,
    ProductSlugTakenError,
    VariantNotFoundError,
)
from memiro.application.errors.pricing import PricingSettingsNotFoundError
from memiro.entities.errors.attribute import (
    InvalidAttributeParentError,
    InvalidAttributeValueSetError,
    InvalidFactorRateError,
)
from memiro.entities.errors.pricing import DuplicateSizeSurchargeError, InvalidSurchargeFactorError
from memiro.entities.errors.product import (
    DuplicateProductImageError,
    DuplicateVariantError,
    InvalidProductSlugError,
    InvalidQuantityError,
    InvalidVariantConfigurationError,
    InvalidVariantSortOrderError,
    ProductSectionNotEmptyError,
)
from memiro_common.errors import AppError
from memiro_common.logger import Logger

UNKNOWN_REFUSAL = "Запись отклонена."

REFUSAL_MESSAGES: dict[type[AppError], str] = {
    AttributeNotFoundError: "Атрибут не найден: похоже, его удалили в другом окне.",
    CategoryNotFoundError: "Раздел не найден: выберите другой.",
    InvalidAttributeParentError: "Атрибут зависит только от атрибутов своего раздела, и круг зависимостей запрещён.",
    InvalidAttributeValueSetError: "Набор значений не описывает этот атрибут: числовому нужна одна строка тарифа.",
    InvalidFactorRateError: "Тариф-множитель должен быть больше нуля.",
    AttributeValueInUseError: "Значение нельзя убрать: его объявляют товары.",
    AttributeInUseError: "Атрибут нельзя удалить: он ещё кому-то нужен.",
    PricingSettingsNotFoundError: "Параметров расчёта на сайте нет: заведите строку параметров.",
    InvalidSurchargeFactorError: "Коэффициент ступени должен быть больше единицы: наценка выключается пустой таблицей.",
    DuplicateSizeSurchargeError: "Две ступени не начинаются с одного размера: оставьте одну.",
    ProductNotFoundError: "Товар не найден: похоже, его удалили в другом окне.",
    ProductImageNotFoundError: "Фотография не найдена: похоже, её убрали в другом окне.",
    DuplicateProductImageError: "Такая фотография у товара уже есть.",
    ProductSlugTakenError: "Этот адрес уже занят другим товаром: придумайте другой.",
    InvalidProductSlugError: "Адрес товара — латинские слова через дефис, и пустым он выводится из названия.",
    ProductSectionNotEmptyError: (
        "Товар нельзя перенести в другой раздел непустым: сначала снимите объявленные значения и варианты."
    ),
    AttributeValueNotFoundError: "Значение не найдено: оно чужого атрибута или атрибут не из раздела товара.",
    VariantNotFoundError: "Вариант не найден: похоже, его удалили в другом окне.",
    DuplicateVariantError: "Такой вариант уже есть: тот же размер и те же значения.",
    InvalidVariantConfigurationError: (
        "Цену такого варианта посчитать нечем: товар объявил не все платные значения — заполните карточку."
    ),
    InvalidVariantSortOrderError: "Порядок варианта не бывает отрицательным.",
    InvalidQuantityError: "Количество не бывает отрицательным.",
    LockTimeoutError: "Эту строку сейчас правят в другом окне: повторите сохранение.",
}

# The names the refusal carries in its ``meta``, in the owner's words.
HOLDER_TITLES = {"products": "Товары", "attributes": "Атрибуты"}

logger: Logger = structlog.get_logger(__name__)


def refusal_text(refusal: AppError) -> str:
    """Say a domain refusal in the owner's language, naming what still holds the row."""
    message = REFUSAL_MESSAGES.get(type(refusal))
    if message is None:
        logger.critical("Refusal is missing from the admin's wording table", code=type(refusal).code)
        message = UNKNOWN_REFUSAL
    return " ".join([message, *_holders(refusal.meta)])


def _holders(meta: dict[str, Any] | None) -> Iterator[str]:
    """List what the refusal names, one sentence per kind of holder."""
    for key, title in HOLDER_TITLES.items():
        names: list[str] = (meta or {}).get(key, [])
        if names:
            yield f"{title}: {', '.join(names)}."
