# Реестр ошибок

Машинный `code` — внешний контракт API: по нему витрина и админка выбирают
русскую формулировку, и потому код не меняется молча (§4, AGENTS.md). Таблица
соответствия HTTP живёт в одном месте кода —
`presentation/fast_api/error_handlers.py`; эта страница — её человеческое
зеркало и пополняется тем же PR, что и ошибка.

| Код | HTTP | Класс | Когда |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | — (FastAPI) | Тело или параметры запроса не прошли границы формы |
| `PRODUCT_NOT_FOUND` | 404 | `ProductNotFoundError` | Товара с названным идентификатором нет |
| `VARIANT_NOT_FOUND` | 404 | `VariantNotFoundError` | Вариант не принадлежит названному товару |
| `ATTRIBUTE_VALUE_NOT_FOUND` | 404 | `AttributeValueNotFoundError` | Значения нет, оно чужого атрибута или атрибут не объявлен у товара |
| `PRICING_SETTINGS_NOT_FOUND` | 404 | `PricingSettingsNotFoundError` | Параметры расчёта в базе не заведены |
| `INVALID_FACTOR_RATE` | 400 | `InvalidFactorRateError` | У значения с единицей `FACTOR` нулевой коэффициент |
| `NEGATIVE_MEASURE` | 400 | `NegativeMeasureError` | Величина получила отрицательное значение |
| `EMPTY_DIMENSIONS` | 400 | `EmptyDimensionsError` | Сторона изделия не строго положительна |
| `INVALID_SURCHARGE_FACTOR` | 400 | `InvalidSurchargeFactorError` | Коэффициент ступени наценки за размер не больше единицы |
| `DUPLICATE_SIZE_SURCHARGE` | 400 | `DuplicateSizeSurchargeError` | Две ступени наценки за размер начинаются на одной границе |
| `INVALID_VARIANT_CONFIGURATION` | 400 | `InvalidVariantConfigurationError` | Конфигурация варианта не описывает полностью считаемый товар |
| `INVALID_VARIANT_SORT_ORDER` | 400 | `InvalidVariantSortOrderError` | Порядок варианта отрицательный |
| `DUPLICATE_VARIANT` | 409 | `DuplicateVariantError` | У товара уже есть вариант такого размера и с теми же overrides |
| `INTERNAL_ERROR` | 500 | — | Дефект: незамапленная `AppError` или неожиданное исключение |

Пятисотка тоже приходит этой формой: глобальных хендлера три — `AppError`,
ошибка валидации FastAPI и `Exception`, — и `RuntimeError` домена уезжает
наружу как `{code, message, meta}`, а не текстовой страницей фреймворка.

Форма ответа одна на всё:

```json
{"code": "PRODUCT_NOT_FOUND", "message": "Product not found", "meta": null}
```

`message` — английская строка домена, не текст для покупателя: русские
формулировки собирает витрина по коду (решение 33).

`NEGATIVE_MEASURE` и `EMPTY_DIMENSIONS` доменные и потому в таблице есть, хотя
сегодня до них не доходит: границы формы расчёта отсекают такой ввод раньше
(422). Незамапленная ошибка — `logger.critical` и 500, поэтому в таблице
числятся и те коды, которых наружу ещё не видно.
