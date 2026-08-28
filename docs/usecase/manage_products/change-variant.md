# Изменение предпосчитанного варианта

**Актор:** владелец, установленный Django-презентацией.

## Input

Путь передаёт `product_id` и `variant_id`; `ChangeVariantForm` несёт новые
`width_mm`, `height_mm`, `overrides` и `sort_order`. Цены во входе нет.

## Output

Нет тела результата.

## Business Rules

1. Форма соблюдает те же application limits и единственность представления,
   что добавление — иначе `VALIDATION_ERROR` (422).
2. Товар существует — иначе `PRODUCT_NOT_FOUND` (404).
3. Вариант принадлежит товару — иначе `VARIANT_NOT_FOUND` (404).
4. Параметры расчёта существуют — иначе `PRICING_SETTINGS_NOT_FOUND` (404).
5. Overrides разрешаются по справочнику категории — иначе
   `ATTRIBUTE_VALUE_NOT_FOUND` (404).
6. Конфигурация полностью считается — иначе
   `INVALID_VARIANT_CONFIGURATION` (400).
7. Порядок неотрицательный — иначе `INVALID_VARIANT_SORT_ORDER` (400).
8. После исключения изменяемого варианта дубля размера и overrides нет — иначе
   `DUPLICATE_VARIANT` (409).
9. Цена пересчитывается тем же владельческим вопросом, вариант заменяется,
   `price_from` пересчитывается последней строкой и транзакция коммитится.
   Ошибки нет.

## Errors

`VALIDATION_ERROR` (422), `PRODUCT_NOT_FOUND` (404), `VARIANT_NOT_FOUND`
(404), `PRICING_SETTINGS_NOT_FOUND` (404), `ATTRIBUTE_VALUE_NOT_FOUND` (404),
`INVALID_VARIANT_CONFIGURATION` (400), `INVALID_VARIANT_SORT_ORDER` (400),
`DUPLICATE_VARIANT` (409).
