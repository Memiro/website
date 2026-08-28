# Размножение предпосчитанного варианта по размеру

**Актор:** владелец, установленный Django-презентацией.

Владелец сохраняет overrides и порядок исходного варианта, меняя только
размер. Цена нового ребёнка считается заново.

## Input

Путь передаёт `product_id` и `variant_id`; `DuplicateVariantWithSizeForm`
содержит `width_mm` и `height_mm`.

## Output

`CreatedVariant` с id нового ребёнка.

## Business Rules

1. Стороны соблюдают application limits — иначе `VALIDATION_ERROR` (422).
2. Товар существует — иначе `PRODUCT_NOT_FOUND` (404).
3. Исходный вариант принадлежит товару — иначе `VARIANT_NOT_FOUND` (404).
4. Параметры расчёта существуют — иначе `PRICING_SETTINGS_NOT_FOUND` (404).
5. Конфигурация с прежними overrides и новым размером полностью считается —
   иначе `INVALID_VARIANT_CONFIGURATION` (400).
6. Варианта с новым повёрнутым размером и теми же overrides ещё нет — иначе
   `DUPLICATE_VARIANT` (409).
7. Цена нового варианта считается владельческим вопросом без покупательских
   гейтов, но с наценкой за размер; исходный вариант не меняется. Ошибки нет.
8. Новый вариант добавляется, `price_from` пересчитывается последней строкой и
   одна транзакция агрегата коммитится. Ошибки нет.

## Errors

`VALIDATION_ERROR` (422), `PRODUCT_NOT_FOUND` (404), `VARIANT_NOT_FOUND`
(404), `PRICING_SETTINGS_NOT_FOUND` (404),
`INVALID_VARIANT_CONFIGURATION` (400), `DUPLICATE_VARIANT` (409).
