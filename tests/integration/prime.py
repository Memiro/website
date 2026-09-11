"""Direct writes that stand in for the admin write path (§14.5.5).

There is no use case that creates a product, an attribute or the pricing
settings yet — the admin brings them with its own slice — so the arrangement
of a pricing test goes straight to the tables through named helpers.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.adapters.db.gateways.site import SELLER_REQUISITES_ID, SITE_CONTACTS_ID
from memiro.adapters.db.tables import (
    attribute_values_table,
    attributes_table,
    categories_table,
    inquiries_table,
    inquiry_items_table,
    landing_conditions_table,
    landings_table,
    pricing_settings_table,
    product_declared_values_table,
    product_images_table,
    product_variants_table,
    products_table,
    seller_requisites_table,
    site_contacts_table,
    works_table,
)
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, ProductId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.inquiry.entity import ConfigurationValue, InquiryConfiguration, InquirySource
from memiro.entities.inquiry.phone import Phone
from memiro.entities.pricing.quotation import PricingVerdict
from memiro_common.clock import SystemClock
from tests.common.factory.catalog import (
    ALUMINIUM,
    BACKLIGHT,
    BLADE,
    CATEGORY,
    CONTOUR,
    FOREIGN_PRODUCT,
    FRAME,
    HEATING,
    HIDDEN_INQUIRY_ITEM,
    INQUIRY,
    INQUIRY_ITEM,
    LANDING,
    LEGACY_INQUIRY,
    LEGACY_INQUIRY_ITEM,
    NO_FRAME,
    NO_HEATING,
    NO_MOUNT,
    PRICED_INQUIRY_ITEM,
    PRODUCT,
    RECTANGULAR,
    REFUSED_INQUIRY_ITEM,
    ROUND,
    SECOND_CATEGORY,
    SECOND_PRODUCT,
    SECOND_WORK,
    SHAPE,
    SILVER,
    SPECIFIED_INQUIRY,
    THIRD_PRODUCT,
    WITH_HEATING,
    WITH_MOUNT,
    WORK,
    canonical_specification,
    demo_attributes,
    demo_cutouts,
    demo_numeric_product,
    demo_product,
    demo_settings,
)

# The arranged catalogue has been in place for a while; an absolute date
# written into the row would rot as the calendar moves past it (§14.6.8).
CATALOG_AGE = timedelta(days=30)

# One instant for the whole arrangement: a row that was created and last
# changed at the same moment is what an untouched catalogue looks like.
CATALOG_STAMP: datetime = SystemClock().now() - CATALOG_AGE


async def prime_dictionary(engine: AsyncEngine) -> None:
    """Insert the demo dictionary and the canonical product it describes."""
    attributes = demo_attributes()
    product = demo_product()
    async with engine.begin() as connection:
        await connection.execute(
            insert(categories_table),
            [
                {
                    "id": product.category_id,
                    "name": "Mirrors",
                    "slug": "mirrors",
                    "sort_order": 1,
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                }
            ],
        )
        await connection.execute(
            insert(attributes_table),
            [
                {
                    "id": attribute.id,
                    "category_id": attribute.category_id,
                    "name": attribute.name,
                    "kind": attribute.kind,
                    "parent_ids": attribute.parent_ids,
                    "is_customer_changeable": attribute.is_customer_changeable,
                    "is_filterable": attribute.is_filterable,
                    "sort_order": attribute.sort_order,
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                }
                for attribute in attributes
            ],
        )
        await connection.execute(
            insert(attribute_values_table),
            [
                {
                    "id": value.id,
                    "attribute_id": attribute.id,
                    "name": value.name,
                    "rate_amount": value.rate.amount,
                    "rate_unit": value.rate.unit,
                    "scaled_by_shape": value.scaled_by_shape,
                    "scaled_by_size_surcharge": value.scaled_by_size_surcharge,
                    "marks_absence": value.marks_absence,
                    "sort_order": value.sort_order,
                }
                for attribute in attributes
                for value in attribute.values
            ],
        )
        await connection.execute(
            insert(products_table),
            [
                {
                    "id": product.id,
                    "category_id": product.category_id,
                    "name": product.name,
                    "slug": product.slug,
                    "description": "A made-to-order mirror.",
                    "is_published": product.is_published,
                    "hides_calculated_price": product.hides_calculated_price,
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                },
            ],
        )
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": product.id,
                    "attribute_id": declared.attribute_id,
                    "value_id": declared.chosen.value_id,
                    "quantity": declared.chosen.quantity,
                }
                for declared in product.declared_values
            ],
        )


async def prime_pricing_settings(engine: AsyncEngine) -> None:
    """Insert the single settings row with the owner's demo bounds."""
    settings = demo_settings()
    async with engine.begin() as connection:
        await connection.execute(
            insert(pricing_settings_table),
            [
                {
                    "id": settings.id,
                    "min_area": settings.min_area,
                    "min_order_total": settings.min_order_total,
                    "max_long_side_mm": settings.max_long_side_mm,
                    "max_short_side_mm": settings.max_short_side_mm,
                    "updated_at": CATALOG_STAMP,
                },
            ],
        )


async def prime_no_pricing_settings(engine: AsyncEngine) -> None:
    """Remove pricing settings to arrange the pre-setup refusal."""
    async with engine.begin() as connection:
        await connection.execute(delete(pricing_settings_table))


async def prime_product_publication(engine: AsyncEngine, *, is_published: bool) -> None:
    """Set whether the canonical product is published."""
    async with engine.begin() as connection:
        await connection.execute(
            update(products_table).where(products_table.c.id == PRODUCT).values(is_published=is_published),
        )


async def prime_second_category(
    engine: AsyncEngine,
    *,
    name: str,
    slug: str,
    sort_order: int,
    is_published: bool,
) -> None:
    """Insert one more category holding a single product of the given publication."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(categories_table),
            [
                {
                    "id": SECOND_CATEGORY,
                    "name": name,
                    "slug": slug,
                    "sort_order": sort_order,
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                }
            ],
        )
        await connection.execute(
            insert(products_table),
            [
                {
                    "id": FOREIGN_PRODUCT,
                    "category_id": SECOND_CATEGORY,
                    "name": "Зеркальный шкаф",
                    "slug": f"{slug}-product",
                    "description": "Another made-to-order mirror.",
                    "is_published": is_published,
                    "hides_calculated_price": False,
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                },
            ],
        )


async def prime_extra_product(engine: AsyncEngine, *, name: str, slug: str, is_published: bool) -> None:
    """Add one more product to the canonical category."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(products_table),
            [
                {
                    "id": SECOND_PRODUCT,
                    "category_id": CATEGORY,
                    "name": name,
                    "slug": slug,
                    "description": "Another made-to-order mirror.",
                    "is_published": is_published,
                    "hides_calculated_price": False,
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                },
            ],
        )


async def prime_priced_neighbours(engine: AsyncEngine) -> None:
    """Add two published neighbours with prices and shapes of their own, so a listing has something to narrow.

    The canonical mirror is rectangular and priceless; the round one is the
    cheapest, the second rectangular one the dearest.
    """
    async with engine.begin() as connection:
        await connection.execute(
            insert(products_table),
            [
                {
                    "id": SECOND_PRODUCT,
                    "category_id": CATEGORY,
                    "name": "Круглое зеркало",
                    "slug": "krugloe-zerkalo",
                    "description": "A round made-to-order mirror.",
                    "is_published": True,
                    "hides_calculated_price": False,
                    "price_from": Money(amount=Decimal(4000)),
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                },
                {
                    "id": THIRD_PRODUCT,
                    "category_id": CATEGORY,
                    "name": "Большое зеркало",
                    "slug": "bolshoe-zerkalo",
                    "description": "A large made-to-order mirror.",
                    "is_published": True,
                    "hides_calculated_price": False,
                    "price_from": Money(amount=Decimal(12000)),
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                },
            ],
        )
        await connection.execute(
            insert(product_declared_values_table),
            [
                {"product_id": SECOND_PRODUCT, "attribute_id": SHAPE, "value_id": ROUND, "quantity": None},
                {"product_id": SECOND_PRODUCT, "attribute_id": FRAME, "value_id": NO_FRAME, "quantity": None},
                {"product_id": THIRD_PRODUCT, "attribute_id": SHAPE, "value_id": RECTANGULAR, "quantity": None},
                {"product_id": THIRD_PRODUCT, "attribute_id": FRAME, "value_id": ALUMINIUM, "quantity": None},
            ],
        )


async def prime_site_data(engine: AsyncEngine, *, seller_name: str = "", ogrn: str = "") -> None:
    """Rewrite the single rows the migration created: the storefront is born with contacts, not with a seller."""
    async with engine.begin() as connection:
        await connection.execute(
            update(site_contacts_table)
            .where(site_contacts_table.c.id == SITE_CONTACTS_ID)
            .values(
                city="Санкт-Петербург",
                street="Александра Матросова, 4к2ж",
                phone="+79812304050",
                phone_display="+7 981 230-40-50",
                email="memiro.ru@yandex.ru",
                hours="Ежедневно, по предварительной записи",
                max_link="",
                telegram="https://t.me/memiro_shop",
                vk="https://vk.com/memirospb",
                map_embed="",
                updated_at=CATALOG_STAMP,
            )
        )
        await connection.execute(
            update(seller_requisites_table)
            .where(seller_requisites_table.c.id == SELLER_REQUISITES_ID)
            .values(name=seller_name, ogrn=ogrn, updated_at=CATALOG_STAMP)
        )


async def prime_landing(
    engine: AsyncEngine,
    *,
    is_published: bool = True,
    narrows_by: tuple[AttributeId, AttributeValueId] = (SHAPE, ROUND),
) -> None:
    """Add the landing that narrows the demo category, by default to round mirrors."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(landings_table),
            [
                {
                    "id": LANDING,
                    "category_id": CATEGORY,
                    "slug": "kruglye-zerkala",
                    "title": "Круглые зеркала на заказ — memiro",
                    "heading": "Круглые зеркала",
                    "description": "Круглые зеркала по вашим размерам.",
                    "text": "Круг читается мягче прямоугольника.",  # noqa: RUF001
                    "is_published": is_published,
                    "sort_order": 1,
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                }
            ],
        )
        await connection.execute(
            insert(landing_conditions_table),
            [{"landing_id": LANDING, "attribute_id": narrows_by[0], "value_id": narrows_by[1]}],
        )


async def prime_work(
    engine: AsyncEngine,
    *,
    product_id: ProductId | None = PRODUCT,
    is_published: bool = True,
    sort_order: int = 1,
) -> None:
    """Add the photographed installation of the canonical mirror to the gallery."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(works_table),
            [
                {
                    "id": WORK,
                    "photo_key": "works/hallway.jpg",
                    "product_id": product_id,
                    "title": "Круглое зеркало в прихожей",
                    "description": "Поставили в прихожей квартиры на Ленина.",
                    "is_published": is_published,
                    "sort_order": sort_order,
                }
            ],
        )


async def prime_second_work(engine: AsyncEngine, *, sort_order: int) -> None:
    """Add one more work — a photograph of no catalogued mirror, and without a word under it."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(works_table),
            [
                {
                    "id": SECOND_WORK,
                    "photo_key": "works/bathroom.jpg",
                    "product_id": None,
                    "title": "Зеркало-капля в ванной",
                    "description": "",
                    "is_published": True,
                    "sort_order": sort_order,
                }
            ],
        )


async def count_landings_directly(engine: AsyncEngine) -> int:
    """Count the landing rows outside the interactor, to prove a refusal stored none."""
    async with engine.connect() as connection:
        return (await connection.execute(select(func.count()).select_from(landings_table))).scalar_one()


async def prime_product_images(engine: AsyncEngine) -> None:
    """Give the canonical product two photo keys whose owner order is neither alphabetical nor insertion order."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(product_images_table),
            [
                {"product_id": PRODUCT, "key": "mirror-front.jpg", "sort_order": 2},
                {"product_id": PRODUCT, "key": "mirror-side.jpg", "sort_order": 1},
            ],
        )


async def prime_photograph_of_the_product(engine: AsyncEngine, key: str) -> None:
    """Name one stored photograph in the gallery of the canonical product."""
    async with engine.begin() as connection:
        await connection.execute(insert(product_images_table), [{"product_id": PRODUCT, "key": key, "sort_order": 1}])


async def update_attribute_value_rate_directly(engine: AsyncEngine, value_id: AttributeValueId, rate: Money) -> None:
    """Change a tariff directly to prove a stored inquiry snapshot does not recalculate."""
    async with engine.begin() as connection:
        await connection.execute(
            update(attribute_values_table).where(attribute_values_table.c.id == value_id).values(rate_amount=rate),
        )


async def prime_hidden_calculated_price(engine: AsyncEngine) -> None:
    """Hide the canonical product's calculated price from customers."""
    async with engine.begin() as connection:
        await connection.execute(
            update(products_table).where(products_table.c.id == PRODUCT).values(hides_calculated_price=True),
        )


async def prime_production_limits(
    engine: AsyncEngine,
    *,
    max_long_side_mm: Millimeters,
    max_short_side_mm: Millimeters,
) -> None:
    """Set the production limits of the single pricing-settings row."""
    settings = demo_settings()
    async with engine.begin() as connection:
        await connection.execute(
            update(pricing_settings_table)
            .where(pricing_settings_table.c.id == settings.id)
            .values(
                max_long_side_mm=max_long_side_mm,
                max_short_side_mm=max_short_side_mm,
            ),
        )


async def prime_size_surcharge(engine: AsyncEngine) -> None:
    """Apply the owner's first size-surcharge tier to the demo blade."""
    settings = demo_settings()
    async with engine.begin() as connection:
        await connection.execute(
            update(attribute_values_table)
            .where(attribute_values_table.c.id == SILVER)
            .values(scaled_by_size_surcharge=True),
        )
        await connection.execute(
            text(
                """INSERT INTO size_surcharges (pricing_settings_id, from_long_side_mm, factor)
                   VALUES (:pricing_settings_id, 2200, 1.25)"""
            ),
            {"pricing_settings_id": settings.id},
        )


async def prime_incomplete_declaration(engine: AsyncEngine) -> None:
    """Leave the canonical product's blade declaration unfinished."""
    async with engine.begin() as connection:
        await connection.execute(
            update(product_declared_values_table)
            .where(
                product_declared_values_table.c.product_id == PRODUCT,
                product_declared_values_table.c.attribute_id == BLADE,
            )
            .values(value_id=None, quantity=None),
        )


async def prime_present_dependency(engine: AsyncEngine) -> None:
    """Make backlight present while leaving its dependent heating declaration absent."""
    async with engine.begin() as connection:
        await connection.execute(
            update(product_declared_values_table)
            .where(
                product_declared_values_table.c.product_id == PRODUCT,
                product_declared_values_table.c.attribute_id == BACKLIGHT,
            )
            .values(value_id=CONTOUR),
        )


async def prime_complete_heating_declaration(engine: AsyncEngine) -> None:
    """Declare explicit absence for heating so a customer may turn backlight on."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": PRODUCT,
                    "attribute_id": HEATING,
                    "value_id": NO_HEATING,
                    "quantity": None,
                },
            ],
        )


async def prime_paid_heating_declaration(engine: AsyncEngine) -> None:
    """Make backlight and its paid dependent heating present in the product."""
    async with engine.begin() as connection:
        await connection.execute(
            update(product_declared_values_table)
            .where(
                product_declared_values_table.c.product_id == PRODUCT,
                product_declared_values_table.c.attribute_id == BACKLIGHT,
            )
            .values(value_id=CONTOUR),
        )
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": PRODUCT,
                    "attribute_id": HEATING,
                    "value_id": WITH_HEATING,
                    "quantity": None,
                },
            ],
        )


async def prime_product_without_paid_values(engine: AsyncEngine) -> None:
    """Make every money-bearing declaration of the canonical product free."""
    async with engine.begin() as connection:
        await connection.execute(
            update(attribute_values_table)
            .where(attribute_values_table.c.id.in_([SILVER, ALUMINIUM, WITH_MOUNT]))
            .values(rate_amount=Money(amount=Decimal(0))),
        )


async def prime_one_row_attribute(engine: AsyncEngine) -> None:
    """Leave the mount attribute with a single dictionary row — the shape a numeric attribute needs."""
    async with engine.begin() as connection:
        await connection.execute(delete(attribute_values_table).where(attribute_values_table.c.id == NO_MOUNT))


async def prime_non_changeable_attribute(engine: AsyncEngine) -> None:
    """Prevent customers from changing the canonical product's blade."""
    async with engine.begin() as connection:
        await connection.execute(
            update(attributes_table).where(attributes_table.c.id == BLADE).values(is_customer_changeable=False),
        )


async def prime_numeric_catalog(engine: AsyncEngine) -> None:
    """Replace the demo dictionary and product with one fractional numeric attribute."""
    attribute = demo_cutouts()
    product = demo_numeric_product(quantity=Decimal(1))
    settings = demo_settings()
    value = attribute.values[0]
    async with engine.begin() as connection:
        await connection.execute(delete(product_declared_values_table))
        await connection.execute(delete(attribute_values_table))
        await connection.execute(delete(attributes_table))
        await connection.execute(
            insert(attributes_table),
            [
                {
                    "id": attribute.id,
                    "category_id": attribute.category_id,
                    "name": attribute.name,
                    "kind": attribute.kind,
                    "parent_ids": attribute.parent_ids,
                    "is_customer_changeable": attribute.is_customer_changeable,
                    "is_filterable": attribute.is_filterable,
                    "sort_order": attribute.sort_order,
                    "created_at": CATALOG_STAMP,
                    "updated_at": CATALOG_STAMP,
                },
            ],
        )
        await connection.execute(
            insert(attribute_values_table),
            [
                {
                    "id": value.id,
                    "attribute_id": attribute.id,
                    "name": value.name,
                    "rate_amount": value.rate.amount,
                    "rate_unit": value.rate.unit,
                    "scaled_by_shape": value.scaled_by_shape,
                    "scaled_by_size_surcharge": value.scaled_by_size_surcharge,
                    "marks_absence": value.marks_absence,
                    "sort_order": value.sort_order,
                },
            ],
        )
        await connection.execute(
            update(products_table)
            .where(products_table.c.id == product.id)
            .values(
                category_id=product.category_id,
                name=product.name,
                slug=product.slug,
                is_published=product.is_published,
                hides_calculated_price=product.hides_calculated_price,
            ),
        )
        await connection.execute(
            insert(product_declared_values_table),
            [
                {
                    "product_id": product.id,
                    "attribute_id": product.declared_values[0].attribute_id,
                    "value_id": product.declared_values[0].chosen.value_id,
                    "quantity": product.declared_values[0].chosen.quantity,
                },
            ],
        )
        await connection.execute(
            update(pricing_settings_table)
            .where(pricing_settings_table.c.id == settings.id)
            .values(min_order_total=Money(amount=Decimal(0))),
        )


async def corrupt_a_declaration_directly(engine: AsyncEngine) -> None:
    """Point the product's blade at a value of another attribute."""
    # The foreign keys allow it and no use case can produce it: this is what
    # a defect in the data looks like, and the calculation must not price it.
    async with engine.begin() as connection:
        await connection.execute(
            update(product_declared_values_table)
            .where(
                product_declared_values_table.c.product_id == PRODUCT,
                product_declared_values_table.c.attribute_id == BLADE,
            )
            .values(value_id=ALUMINIUM),
        )


async def count_inquiries_directly(engine: AsyncEngine) -> int:
    """Count the stored inquiries to prove what a refused submission did not leave behind."""
    async with engine.begin() as connection:
        return (await connection.execute(select(func.count()).select_from(inquiries_table))).scalar_one()


async def prime_inquiry_for_the_product(engine: AsyncEngine) -> None:
    """Leave a manager one inquiry whose only position points at the canonical product."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(inquiries_table),
            [
                {
                    "id": INQUIRY,
                    "source": InquirySource.SELECTION,
                    "name": "Ольга",
                    "phone": Phone(value="+79990000000"),
                    "email": None,
                    "comment": "",
                    "consent_version": "2026-01-01",
                    "created_at": CATALOG_STAMP,
                },
            ],
        )
        await connection.execute(
            insert(inquiry_items_table),
            [
                {
                    "id": INQUIRY_ITEM,
                    "inquiry_id": INQUIRY,
                    "product_id": PRODUCT,
                    "product_name": "Зеркало в раме",
                    "price_from": None,
                    "configuration": None,
                    "calculated_price": None,
                    "verdict": PricingVerdict.NOT_PRICEABLE,
                    "wish": "",
                },
            ],
        )


async def prime_legacy_inquiry(engine: AsyncEngine) -> None:
    """Leave a manager one inquiry stored before the snapshot carried the whole specification."""
    async with engine.begin() as connection:
        await connection.execute(
            insert(inquiries_table),
            [
                {
                    "id": LEGACY_INQUIRY,
                    "source": InquirySource.SELECTION,
                    "name": "Пётр",
                    "phone": Phone(value="+79990000001"),
                    "email": "petr@example.test",
                    "comment": "",
                    "consent_version": "2026-01-01",
                    "created_at": CATALOG_STAMP,
                },
            ],
        )
        await connection.execute(
            insert(inquiry_items_table),
            [
                {
                    "id": LEGACY_INQUIRY_ITEM,
                    "inquiry_id": LEGACY_INQUIRY,
                    "product_id": PRODUCT,
                    "product_name": "Зеркало в раме",
                    "price_from": None,
                    "configuration": InquiryConfiguration(
                        dimensions=Dimensions(width=Millimeters(value=800), height=Millimeters(value=600)),
                        values=(ConfigurationValue(attribute_name="Тип полотна", value_name="Графит", quantity=None),),
                    ),
                    "calculated_price": Money(amount=Decimal(10020)),
                    "verdict": PricingVerdict.PRICED,
                    "wish": "Тёплый свет",
                },
            ],
        )


async def prime_specified_inquiry(engine: AsyncEngine) -> None:
    """Leave a manager one inquiry with a priced, a hidden and a refused position, one of a product removed since."""
    dimensions = Dimensions(width=Millimeters(value=800), height=Millimeters(value=600))
    async with engine.begin() as connection:
        await connection.execute(
            insert(inquiries_table),
            [
                {
                    "id": SPECIFIED_INQUIRY,
                    "source": InquirySource.SELECTION,
                    "name": "Мария",
                    "phone": Phone(value="+79990000002"),
                    "email": "maria@example.test",
                    "comment": "",
                    "consent_version": "2026-01-01",
                    "created_at": CATALOG_STAMP,
                },
            ],
        )
        await connection.execute(
            insert(inquiry_items_table),
            [
                {
                    "id": PRICED_INQUIRY_ITEM,
                    "inquiry_id": SPECIFIED_INQUIRY,
                    "product_id": PRODUCT,
                    "product_name": "Зеркало в раме",
                    "price_from": Money(amount=Decimal(8820)),
                    "configuration": InquiryConfiguration(dimensions=dimensions, values=canonical_specification()),
                    "calculated_price": Money(amount=Decimal(8820)),
                    "verdict": PricingVerdict.PRICED,
                    "wish": "Повесить над комодом",
                },
                {
                    "id": HIDDEN_INQUIRY_ITEM,
                    "inquiry_id": SPECIFIED_INQUIRY,
                    "product_id": None,
                    "product_name": "Зеркало из прошлого каталога",
                    "price_from": None,
                    "configuration": InquiryConfiguration(
                        dimensions=dimensions,
                        values=canonical_specification(
                            ConfigurationValue(attribute_name="Тип полотна", value_name="Графит", quantity=None),
                        ),
                    ),
                    "calculated_price": Money(amount=Decimal(10020)),
                    "verdict": PricingVerdict.HIDDEN,
                    "wish": "",
                },
                {
                    "id": REFUSED_INQUIRY_ITEM,
                    "inquiry_id": SPECIFIED_INQUIRY,
                    "product_id": PRODUCT,
                    "product_name": "Зеркало в раме",
                    "price_from": None,
                    "configuration": InquiryConfiguration(
                        dimensions=dimensions,
                        values=canonical_specification(
                            ConfigurationValue(attribute_name="Подсветка", value_name="Контурная", quantity=None),
                        ),
                    ),
                    "calculated_price": None,
                    "verdict": PricingVerdict.SELECTION_NOT_PRICEABLE,
                    "wish": "",
                },
            ],
        )


async def read_inquiry_item_directly(engine: AsyncEngine) -> tuple[ProductId | None, str]:
    """Read what the surviving position still says about the product it was taken from."""
    async with engine.begin() as connection:
        result = await connection.execute(
            select(inquiry_items_table.c.product_id, inquiry_items_table.c.product_name).where(
                inquiry_items_table.c.id == INQUIRY_ITEM,
            ),
        )
        row = result.one()
        return row.product_id, row.product_name


async def count_products_directly(engine: AsyncEngine) -> int:
    """Count the stored products to prove what a refused command did not leave behind."""
    async with engine.begin() as connection:
        return (await connection.execute(select(func.count()).select_from(products_table))).scalar_one()


class StoredProductChildren(NamedTuple):
    """What the tables of the children still hold, whatever product they belong to."""

    declarations: int
    images: int


async def count_product_children_directly(engine: AsyncEngine) -> StoredProductChildren:
    """Count the declarations and the photos still stored, whatever product they belong to."""
    async with engine.begin() as connection:
        declared = await connection.execute(select(func.count()).select_from(product_declared_values_table))
        images = await connection.execute(select(func.count()).select_from(product_images_table))
        return StoredProductChildren(declarations=declared.scalar_one(), images=images.scalar_one())


async def prime_product_in_the_second_section(engine: AsyncEngine) -> None:
    """Put the canonical product in the other section, with nothing declared by the one it left."""
    async with engine.begin() as connection:
        await connection.execute(
            delete(product_declared_values_table).where(
                product_declared_values_table.c.product_id == PRODUCT,
            )
        )
        await connection.execute(
            update(products_table).where(products_table.c.id == PRODUCT).values(category_id=SECOND_CATEGORY),
        )


async def prime_emptied_product(engine: AsyncEngine) -> None:
    """Clear the card of the canonical product the way the owner does before moving it: no declarations, no variants."""
    async with engine.begin() as connection:
        await connection.execute(
            delete(product_declared_values_table).where(product_declared_values_table.c.product_id == PRODUCT),
        )
        await connection.execute(
            delete(product_variants_table).where(product_variants_table.c.product_id == PRODUCT),
        )


async def read_address_holder_directly(engine: AsyncEngine, slug: str) -> ProductId | None:
    """Read which product ended up answering on the contested address."""
    async with engine.begin() as connection:
        result = await connection.execute(select(products_table.c.id).where(products_table.c.slug == slug))
        return result.scalar_one_or_none()
