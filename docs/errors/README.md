# Реестр ошибок

Машинный `code` — внешний контракт API: по нему витрина и админка выбирают
русскую формулировку, и потому код не меняется молча (§4, AGENTS.md). Таблица
соответствия HTTP живёт в одном месте кода —
`presentation/fast_api/error_handlers.py`; эта страница — её человеческое
зеркало и пополняется тем же PR, что и ошибка.

| Код | HTTP | Класс | Когда |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | — (FastAPI) | Тело или параметры запроса не прошли границы формы |
| `CATEGORY_NOT_FOUND` | 404 | `CategoryNotFoundError` | Категории с названным slug нет |
| `LANDING_NOT_FOUND` | 404 | `LandingNotFoundError` | Посадочной с названным slug нет или она снята с публикации |
| `PRODUCT_NOT_FOUND` | 404 | `ProductNotFoundError` | Товара с названным идентификатором нет |
| `PRODUCT_IMAGE_NOT_FOUND` | 404 | `ProductImageNotFoundError` | Ключ не называет ни одной фотографии этого товара |
| `VARIANT_NOT_FOUND` | 404 | `VariantNotFoundError` | Вариант не принадлежит названному товару |
| `WORK_NOT_FOUND` | 404 | `WorkNotFoundError` | Работы с названным идентификатором в галерее нет |
| `ATTRIBUTE_VALUE_NOT_FOUND` | 404 | `AttributeValueNotFoundError` | Значения нет, оно чужого атрибута или атрибут не объявлен у товара |
| `ATTRIBUTE_NOT_FOUND` | 404 | `AttributeNotFoundError` | Атрибута с названным идентификатором нет |
| `PRICING_SETTINGS_NOT_FOUND` | 404 | `PricingSettingsNotFoundError` | Параметры расчёта в базе не заведены |
| `INVALID_FACTOR_RATE` | 400 | `InvalidFactorRateError` | У значения с единицей `FACTOR` нулевой коэффициент |
| `INVALID_ATTRIBUTE_PARENT` | 400 | `InvalidAttributeParentError` | Родитель атрибута не той категории, это сам атрибут или родство замкнулось в круг |
| `INVALID_ATTRIBUTE_VALUE_SET` | 400 | `InvalidAttributeValueSetError` | Набор значений не описывает справочник этого атрибута |
| `NEGATIVE_MEASURE` | 400 | `NegativeMeasureError` | Величина получила отрицательное значение |
| `EMPTY_DIMENSIONS` | 400 | `EmptyDimensionsError` | Сторона изделия не строго положительна |
| `INVALID_SURCHARGE_FACTOR` | 400 | `InvalidSurchargeFactorError` | Коэффициент ступени наценки за размер не больше единицы |
| `DUPLICATE_SIZE_SURCHARGE` | 400 | `DuplicateSizeSurchargeError` | Две ступени наценки за размер начинаются на одной границе |
| `INVALID_VARIANT_CONFIGURATION` | 400 | `InvalidVariantConfigurationError` | Конфигурация варианта не описывает полностью считаемый товар |
| `INVALID_VARIANT_SORT_ORDER` | 400 | `InvalidVariantSortOrderError` | Порядок варианта отрицательный |
| `INVALID_QUANTITY` | 400 | `InvalidQuantityError` | Числовой расход настроенного значения отрицательный |
| `IMAGE_NOT_PROCESSABLE` | 400 | `ImageNotProcessableError` | Загруженный файл не читается как фотография: производные из него не сделать |
| `INVALID_PRODUCT_SLUG` | 400 | `InvalidProductSlugError` | Из названия товара не выводится ни одного символа адреса |
| `INVALID_LANDING_SLUG` | 400 | `InvalidLandingSlugError` | Из заголовка посадочной не выводится ни одного символа адреса |
| `INVALID_LANDING_NARROWING` | 400 | `InvalidLandingNarrowingError` | Сужение посадочной пустое, шире двух атрибутов, чужое или равно всей категории |
| `DUPLICATE_VARIANT` | 409 | `DuplicateVariantError` | У товара уже есть вариант такого размера и с теми же итоговыми значениями |
| `DUPLICATE_PRODUCT_IMAGE` | 409 | `DuplicateProductImageError` | Фотография с таким ключом у товара уже есть |
| `PRODUCT_SLUG_TAKEN` | 409 | `ProductSlugTakenError` | Публичный адрес товара занят другим товаром |
| `LANDING_SLUG_TAKEN` | 409 | `LandingSlugTakenError` | Адрес посадочной занят другой посадочной |
| `PRODUCT_SECTION_NOT_EMPTY` | 409 | `ProductSectionNotEmptyError` | Товар переносят в другой раздел, а он ещё объявляет значения или держит варианты |
| `ATTRIBUTE_VALUE_IN_USE` | 409 | `AttributeValueInUseError` | Удаляемое значение объявлено товарами или сужает посадочную; `meta.products` и `meta.landings` — их названия |
| `ATTRIBUTE_IN_USE` | 409 | `AttributeInUseError` | Удаляемый атрибут объявлен товарами, назван родителем другого или сужает посадочную; `meta.products`, `meta.attributes` и `meta.landings` — их названия |
| `CONSENT_REQUIRED` | 400 | `ConsentRequiredError` | Посетитель не согласился на обработку ПД |
| `INVALID_PHONE` | 400 | `InvalidPhoneError` | Телефон в заявке не похож на телефон: не 10–15 цифр |
| `EMPTY_INQUIRY` | 400 | `EmptyInquiryError` | Подборка не содержит позиции |
| `INQUIRY_SOURCE_NOT_ACCEPTED` | 400 | `InquirySourceNotAcceptedError` | Новый запрос использовал исторический источник `PRODUCT_CARD` |
| `INVALID_INQUIRY_CONTENTS` | 400 | `InvalidInquiryContentsError` | Поля заявки не соответствуют её источнику |
| `LOCK_TIMEOUT` | 429 | `LockTimeoutError` | Строку агрегата не удалось заблокировать за отведённое ожидание — повторите запрос |
| `CONCURRENT_CHANGE` | 429 | — (`IntegrityError`) | Гонка проиграна на инварианте базы (уникальный отпечаток варианта, занятый адрес товара или посадочной) — повторите запрос |
| `INTERNAL_ERROR` | 500 | — | Дефект: незамапленная `AppError` или неожиданное исключение |

Пятисотка тоже приходит этой формой: глобальных хендлера четыре — `AppError`,
ошибка валидации FastAPI, `IntegrityError` и `Exception`, — и `RuntimeError`
домена уезжает наружу как `{code, message, meta}`, а не текстовой страницей
фреймворка.

Конфликт базы — не дефект: `IntegrityError` гейтвеи не глотают, он доезжает до
глобального хендлера. Гонкой считаются только нарушения уникальности (23505) и
исключающего ограничения (23P01) — их повтор способен выиграть; сломанная
ссылка или проваленный check повтором не чинятся и остаются 500 с трейсбеком,
иначе клиент кружил бы на 429 вечно, а мониторинг молчал.

Ожидание блокировки ограничено настройкой `lock_timeout` соединения
(`DbConfig.lock_timeout_ms`). Отказ в блокировке (55P03) переводится в
`LockTimeoutError` в двух местах: гейтвей переводит блокировку, которую берёт
сам, а глобальный хендлер — тот же отказ, прилетевший из `flush` или `commit`
голым `DBAPIError`.

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
