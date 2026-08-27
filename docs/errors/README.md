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
| `ATTRIBUTE_VALUE_NOT_FOUND` | 404 | `AttributeValueNotFoundError` | Значения нет, оно чужого атрибута или атрибут не объявлен у товара |
| `PRICING_SETTINGS_NOT_FOUND` | 404 | `PricingSettingsNotFoundError` | Параметры расчёта в базе не заведены |
| `INTERNAL_ERROR` | 500 | — | Дефект: незамапленная `AppError` или неожиданное исключение |

Форма ответа одна на всё:

```json
{"code": "PRODUCT_NOT_FOUND", "message": "Product not found", "meta": null}
```

`message` — английская строка домена, не текст для покупателя: русские
формулировки собирает витрина по коду (решение 33).
