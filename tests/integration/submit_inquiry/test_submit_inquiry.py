from collections.abc import Sequence
from decimal import Decimal
from uuid import uuid4

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.customer_selection import Selection
from memiro.application.common.gateway.inquiry import InquiryGateway
from memiro.application.common.input_limits import (
    MAX_COMMENT_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_INQUIRY_ITEMS,
    MAX_NAME_LENGTH,
    MAX_PHONE_LENGTH,
    MAX_SELECTIONS,
    MAX_WISH_LENGTH,
)
from memiro.application.submit_inquiry import InquiryItemForm, InquirySource, SubmitInquiryForm
from memiro.entities.common.identifiers import InquiryItemId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.inquiry.entity import ConfigurationValue, InquiryConfiguration, InquiryItem
from memiro.entities.pricing.quotation import PricingVerdict
from tests.common.factory.catalog import BLADE, GRAPHITE, PRODUCT
from tests.common.factory.pricing import SelectionFactory
from tests.integration.api_client import ApiClient
from tests.integration.prime import (
    count_inquiries_directly,
    prime_product_publication,
    prime_production_limits,
    update_attribute_value_rate_directly,
)

pytestmark = pytest.mark.usefixtures("catalog")


def _item(**overrides: object) -> InquiryItemForm:
    """Build the canonical item — 800 x 600 of the demo mirror — with the test's own changes."""
    return InquiryItemForm(
        product_id=PRODUCT,
        width_mm=800,
        height_mm=600,
        selections=[],
        wish="",
    ).model_copy(update=overrides)


def _form(**overrides: object) -> SubmitInquiryForm:
    """Build a consented selection of one canonical item with the test's own changes."""
    return SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=True,
        comment="",
        items=[_item()],
    ).model_copy(update=overrides)


def _configuration(width_mm: int, height_mm: int, *values: ConfigurationValue) -> InquiryConfiguration:
    """Build the frozen configuration of one item snapshot."""
    return InquiryConfiguration(
        dimensions=Dimensions(width=Millimeters(value=width_mm), height=Millimeters(value=height_mm)),
        values=values,
    )


def _snapshot(
    item_id: InquiryItemId,
    *,
    configuration: InquiryConfiguration | None,
    calculated_price: Money | None,
    wish: str,
    verdict: PricingVerdict = PricingVerdict.PRICED,
) -> InquiryItem:
    """Build the whole item snapshot a stored inquiry is compared against."""
    return InquiryItem(
        id=item_id,
        product_id=PRODUCT,
        product_name="Зеркало в раме",
        price_from=None,
        configuration=configuration,
        calculated_price=calculated_price,
        verdict=verdict,
        wish=wish,
    )


def _by_wish(items: Sequence[InquiryItem]) -> list[InquiryItem]:
    """Order the item snapshots by wish — the aggregate keeps them ordered by their random identifier."""
    return sorted(items, key=lambda item: item.wish)


# One entry per input bound of the form; the code pins the layer that catches
# it — the form itself, before any aggregate is read.
OVER_THE_INPUT_BOUNDS: list[tuple[dict[str, object], str]] = [
    ({"items": [_item()] * (MAX_INQUIRY_ITEMS + 1)}, "VALIDATION_ERROR"),
    ({"name": "a" * (MAX_NAME_LENGTH + 1)}, "VALIDATION_ERROR"),
    ({"phone": "9" * (MAX_PHONE_LENGTH + 1)}, "VALIDATION_ERROR"),
    ({"email": "a" * (MAX_EMAIL_LENGTH + 1)}, "VALIDATION_ERROR"),
    ({"comment": "a" * (MAX_COMMENT_LENGTH + 1)}, "VALIDATION_ERROR"),
    ({"items": [_item(wish="a" * (MAX_WISH_LENGTH + 1))]}, "VALIDATION_ERROR"),
    ({"items": [_item(selections=SelectionFactory.batch(MAX_SELECTIONS + 1))]}, "VALIDATION_ERROR"),
]


async def test_a_customer_submits_multiple_configured_mirrors_in_one_inquiry(
    api_client: ApiClient,
    request_container: AsyncContainer,
) -> None:
    """A SELECTION inquiry stores every configured item in one aggregate."""
    form = _form(
        email="anna@example.test",
        items=[
            _item(),
            _item(
                width_mm=900,
                height_mm=900,
                selections=[Selection(attribute_id=BLADE, value_id=GRAPHITE)],
                wish="Warm light",
            ),
        ],
    )

    created = (await api_client.submit_inquiry(form)).assert_status(200).ensure_content()
    gateway: InquiryGateway = await request_container.get(InquiryGateway)
    inquiry = await gateway.get(created.id)

    assert inquiry is not None
    stored = _by_wish(inquiry.items)
    # Mirror of price_product in entities/pricing/pricing_service.py, by hand
    # from the owner's workbook: 0.48 m2 x 4500 + 2.8 lm x 2200 + 500 = 8 820
    # -> 8 900, and 0.81 m2 x 7000 + 3.6 lm x 2200 + 500 = 14 090 -> 14 100.
    assert stored == [
        _snapshot(
            stored[0].id,
            configuration=_configuration(800, 600),
            calculated_price=Money(Decimal(8900)),
            wish="",
        ),
        _snapshot(
            stored[1].id,
            configuration=_configuration(
                900,
                900,
                ConfigurationValue(attribute_name="Тип полотна", value_name="Графит", quantity=None),
            ),
            calculated_price=Money(Decimal(14100)),
            wish="Warm light",
        ),
    ]


async def test_an_inquiry_keeps_the_configuration_and_price_it_was_shown(
    api_client: ApiClient,
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """An item snapshot does not change after its BLADE tariff changes."""
    form = _form(
        items=[
            _item(
                selections=[Selection(attribute_id=BLADE, value_id=GRAPHITE)],
                wish="Warm light",
            ),
        ],
    )

    created = (await api_client.submit_inquiry(form)).assert_status(200).ensure_content()
    await update_attribute_value_rate_directly(engine, GRAPHITE, Money(Decimal(1)))
    gateway: InquiryGateway = await request_container.get(InquiryGateway)
    inquiry = await gateway.get(created.id)

    assert inquiry is not None
    # Mirror of price_product in entities/pricing/pricing_service.py, by hand:
    # 0.48 m2 x 7000 + 2.8 lm x 2200 + 500 = 10 020 -> 10 100.
    assert inquiry.items[0] == _snapshot(
        inquiry.items[0].id,
        configuration=_configuration(
            800,
            600,
            ConfigurationValue(attribute_name="Тип полотна", value_name="Графит", quantity=None),
        ),
        calculated_price=Money(Decimal(10100)),
        wish="Warm light",
    )


async def test_an_inquiry_beyond_production_limits_keeps_that_verdict(
    api_client: ApiClient,
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """An item the studio cannot make is stored with BEYOND_LIMITS and no price."""
    await prime_production_limits(
        engine,
        max_long_side_mm=Millimeters(value=700),
        max_short_side_mm=Millimeters(value=500),
    )

    created = (await api_client.submit_inquiry(_form())).assert_status(200).ensure_content()
    gateway: InquiryGateway = await request_container.get(InquiryGateway)
    inquiry = await gateway.get(created.id)

    assert inquiry is not None
    assert inquiry.items[0] == _snapshot(
        inquiry.items[0].id,
        configuration=_configuration(800, 600),
        calculated_price=None,
        wish="",
        verdict=PricingVerdict.BEYOND_LIMITS,
    )


async def test_a_not_priceable_product_keeps_no_configuration_in_an_inquiry(
    api_client: ApiClient,
    engine: AsyncEngine,
    request_container: AsyncContainer,
) -> None:
    """A NOT_PRICEABLE item stores no configuration snapshot."""
    await prime_product_publication(engine, is_published=False)

    created = (await api_client.submit_inquiry(_form())).assert_status(200).ensure_content()
    gateway: InquiryGateway = await request_container.get(InquiryGateway)
    inquiry = await gateway.get(created.id)

    assert inquiry is not None
    assert inquiry.items[0] == _snapshot(
        inquiry.items[0].id,
        configuration=None,
        calculated_price=None,
        wish="",
        verdict=PricingVerdict.NOT_PRICEABLE,
    )


async def test_a_new_inquiry_rejects_the_historical_product_card_source(api_client: ApiClient) -> None:
    """A PRODUCT_CARD inquiry is rejected with INQUIRY_SOURCE_NOT_ACCEPTED before its item is read."""
    form = _form(source=InquirySource.PRODUCT_CARD, items=[_item(product_id=uuid4())])

    response = await api_client.submit_inquiry(form)

    response.assert_error(400, "INQUIRY_SOURCE_NOT_ACCEPTED")


async def test_an_inquiry_without_consent_is_rejected_before_its_item_is_read(api_client: ApiClient) -> None:
    """A missing consent is rejected with CONSENT_REQUIRED without reading the named product."""
    form = _form(consent=False, items=[_item(product_id=uuid4())])

    response = await api_client.submit_inquiry(form)

    response.assert_error(400, "CONSENT_REQUIRED")


async def test_a_selection_without_items_is_rejected(api_client: ApiClient) -> None:
    """An empty selection is rejected with EMPTY_INQUIRY — the HTTP pair of the domain rule."""
    form = _form(items=[])

    response = await api_client.submit_inquiry(form)

    response.assert_error(400, "EMPTY_INQUIRY")


@pytest.mark.parametrize(("patch", "code"), OVER_THE_INPUT_BOUNDS)
async def test_an_inquiry_fails_if_a_field_is_over_its_input_bound(
    api_client: ApiClient,
    patch: dict[str, object],
    code: str,
) -> None:
    """A field one unit over its production bound is refused by the form itself."""
    dishonest = _form(**patch)

    response = await api_client.submit_inquiry(dishonest)

    response.assert_error(422, code)


async def test_an_inquiry_naming_an_unknown_product_stores_nothing(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """An item naming a product that does not exist is refused with PRODUCT_NOT_FOUND."""
    form = _form(items=[_item(), _item(product_id=uuid4())])

    response = await api_client.submit_inquiry(form)

    response.assert_error(404, "PRODUCT_NOT_FOUND")
    assert await count_inquiries_directly(engine) == 0
