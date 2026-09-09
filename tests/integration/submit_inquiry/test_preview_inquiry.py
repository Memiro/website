from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.common.customer_selection import Selection
from memiro.application.common.input_limits import MAX_INQUIRY_ITEMS, MAX_SELECTIONS, MAX_WISH_LENGTH
from memiro.application.submit_inquiry import (
    InquiryItemForm,
    InquiryPreview,
    InquirySource,
    PreviewedConfiguration,
    PreviewedItem,
    PreviewedValue,
    PreviewInquiryForm,
    SubmitInquiryForm,
)
from memiro.entities.common.measure import Millimeters
from memiro.entities.inquiry.entity import ConfigurationValue
from memiro.entities.pricing.quotation import PricingVerdict
from tests.common.factory.catalog import BACKLIGHT, BLADE, CONTOUR, GRAPHITE, PRODUCT, canonical_specification
from tests.common.factory.pricing import SelectionFactory
from tests.integration.api_client import ApiClient
from tests.integration.prime import (
    count_inquiries_directly,
    prime_hidden_calculated_price,
    prime_product_publication,
    prime_product_without_paid_values,
    prime_production_limits,
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


def _preview(*items: InquiryItemForm) -> PreviewInquiryForm:
    """Build a preview request of the given items, the bounds of the form left to the API."""
    return PreviewInquiryForm.model_construct(items=list(items))


def _specified(width_mm: int, height_mm: int, *chosen: PreviewedValue) -> PreviewedConfiguration:
    """Build the canonical specification with the customer's choices standing in for the declared values."""
    values = canonical_specification(
        *(
            ConfigurationValue(attribute_name=v.attribute_name, value_name=v.value_name, quantity=v.quantity)
            for v in chosen
        )
    )
    return PreviewedConfiguration(
        width_mm=width_mm,
        height_mm=height_mm,
        values=[
            PreviewedValue(attribute_name=v.attribute_name, value_name=v.value_name, quantity=v.quantity)
            for v in values
        ],
    )


def _previewed(
    *,
    verdict: PricingVerdict = PricingVerdict.PRICED,
    price: Decimal | None,
    configuration: PreviewedConfiguration | None,
    wish: str = "",
) -> PreviewedItem:
    """Build the whole projection of one available canonical position."""
    return PreviewedItem(
        product_id=PRODUCT,
        is_available=True,
        product_name="Зеркало в раме",
        price_from=None,
        verdict=verdict,
        price=price,
        configuration=configuration,
        wish=wish,
    )


# One entry per input bound of the form; the code pins the layer that catches
# it — the form itself, before any aggregate is read.
OVER_THE_INPUT_BOUNDS: list[tuple[list[InquiryItemForm], str]] = [
    ([_item()] * (MAX_INQUIRY_ITEMS + 1), "VALIDATION_ERROR"),
    ([], "VALIDATION_ERROR"),
    ([_item(wish="a" * (MAX_WISH_LENGTH + 1))], "VALIDATION_ERROR"),
    ([_item(selections=SelectionFactory.batch(MAX_SELECTIONS + 1))], "VALIDATION_ERROR"),
]


async def test_a_customer_previews_the_specification_and_the_price_of_every_position(
    api_client: ApiClient,
) -> None:
    """A preview answers every position in the order it came, with the whole specification and the price."""
    form = _preview(
        _item(),
        _item(
            width_mm=900,
            height_mm=900,
            selections=[Selection(attribute_id=BLADE, value_id=GRAPHITE)],
            wish="Warm light",
        ),
    )

    preview = (await api_client.preview_inquiry(form)).assert_status(200).ensure_content()

    # Mirror of price_product in entities/pricing/pricing_service.py, by hand
    # from the owner's workbook: 0.48 m2 x 4500 + 2.8 lm x 2200 + 500 = 8 820
    # and 0.81 m2 x 7000 + 3.6 lm x 2200 + 500 = 14 090.
    assert preview == InquiryPreview(
        items=[
            _previewed(price=Decimal(8820), configuration=_specified(800, 600)),
            _previewed(
                price=Decimal(14090),
                configuration=_specified(
                    900,
                    900,
                    PreviewedValue(attribute_name="Тип полотна", value_name="Графит", quantity=None),
                ),
                wish="Warm light",
            ),
        ]
    )


async def test_a_hidden_price_stays_out_of_the_preview(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A HIDDEN position keeps its specification and names no price, as the card did not (rule 20)."""
    await prime_hidden_calculated_price(engine)

    preview = (await api_client.preview_inquiry(_preview(_item()))).assert_status(200).ensure_content()

    assert preview.items == [
        _previewed(verdict=PricingVerdict.HIDDEN, price=None, configuration=_specified(800, 600)),
    ]


async def test_a_product_without_a_calculation_is_previewed_without_a_configuration(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A NOT_PRICEABLE position is still a position, with no configuration to show (rule 8)."""
    await prime_product_without_paid_values(engine)

    preview = (await api_client.preview_inquiry(_preview(_item()))).assert_status(200).ensure_content()

    assert preview.items == [_previewed(verdict=PricingVerdict.NOT_PRICEABLE, price=None, configuration=None)]


async def test_a_size_beyond_production_is_previewed_with_its_verdict(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A BEYOND_LIMITS position names its verdict and its specification, and no price."""
    await prime_production_limits(
        engine,
        max_long_side_mm=Millimeters(value=700),
        max_short_side_mm=Millimeters(value=500),
    )

    preview = (await api_client.preview_inquiry(_preview(_item()))).assert_status(200).ensure_content()

    assert preview.items == [
        _previewed(verdict=PricingVerdict.BEYOND_LIMITS, price=None, configuration=_specified(800, 600)),
    ]


async def test_a_choice_the_calculation_refused_is_previewed_with_its_specification(
    api_client: ApiClient,
) -> None:
    """A SELECTION_NOT_PRICEABLE position shows the refused choice inside the whole specification."""
    form = _preview(_item(selections=[Selection(attribute_id=BACKLIGHT, value_id=CONTOUR)]))

    preview = (await api_client.preview_inquiry(form)).assert_status(200).ensure_content()

    assert preview.items == [
        _previewed(
            verdict=PricingVerdict.SELECTION_NOT_PRICEABLE,
            price=None,
            configuration=_specified(
                800,
                600,
                PreviewedValue(attribute_name="Подсветка", value_name="Контурная", quantity=None),
            ),
        ),
    ]


async def test_a_removed_product_is_previewed_as_unavailable_next_to_the_others(
    api_client: ApiClient,
) -> None:
    """A position naming a product that is gone is answered empty, and the other positions are answered."""
    gone = uuid4()
    form = _preview(_item(product_id=gone, wish="Warm light"), _item())

    preview = (await api_client.preview_inquiry(form)).assert_status(200).ensure_content()

    assert preview.items == [
        PreviewedItem(
            product_id=gone,
            is_available=False,
            product_name=None,
            price_from=None,
            verdict=None,
            price=None,
            configuration=None,
            wish="Warm light",
        ),
        _previewed(price=Decimal(8820), configuration=_specified(800, 600)),
    ]


async def test_an_unpublished_product_is_previewed_as_unavailable(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """A product taken off the storefront is answered as unavailable, not as a priced position."""
    await prime_product_publication(engine, is_published=False)

    preview = (await api_client.preview_inquiry(_preview(_item()))).assert_status(200).ensure_content()

    assert preview.items == [
        PreviewedItem(
            product_id=PRODUCT,
            is_available=False,
            product_name=None,
            price_from=None,
            verdict=None,
            price=None,
            configuration=None,
            wish="",
        ),
    ]


async def test_a_preview_stores_nothing_and_sends_no_email(
    notifying_api_client: ApiClient,
    engine: AsyncEngine,
    smtp_server: tuple[int, list[str]],
) -> None:
    """A preview is a reading: no inquiry is stored and the manager hears nothing."""
    response = await notifying_api_client.preview_inquiry(_preview(_item()))

    _, received_emails = smtp_server

    assert response.assert_status(200).ensure_content().items
    assert await count_inquiries_directly(engine) == 0
    assert received_emails == []


async def test_a_submitted_inquiry_answers_with_the_positions_the_preview_showed(
    api_client: ApiClient,
) -> None:
    """The answer of a submission is the same projection as the preview of the same selection (rule 20)."""
    items = [
        _item(),
        _item(
            width_mm=900,
            height_mm=900,
            selections=[Selection(attribute_id=BLADE, value_id=GRAPHITE)],
            wish="Warm light",
        ),
    ]
    form = SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=True,
        comment="",
        items=items,
    )

    created = (await api_client.submit_inquiry(form)).assert_status(200).ensure_content()

    # The very list the preview test above expects of the same selection.
    assert created.items == [
        _previewed(price=Decimal(8820), configuration=_specified(800, 600)),
        _previewed(
            price=Decimal(14090),
            configuration=_specified(
                900,
                900,
                PreviewedValue(attribute_name="Тип полотна", value_name="Графит", quantity=None),
            ),
            wish="Warm light",
        ),
    ]


async def test_a_hidden_price_stays_out_of_the_submit_answer_too(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The summary after a submission names no HIDDEN price either."""
    await prime_hidden_calculated_price(engine)
    form = SubmitInquiryForm(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        consent=True,
        comment="",
        items=[_item()],
    )

    created = (await api_client.submit_inquiry(form)).assert_status(200).ensure_content()

    assert created.items == [
        _previewed(verdict=PricingVerdict.HIDDEN, price=None, configuration=_specified(800, 600)),
    ]


@pytest.mark.parametrize(("items", "code"), OVER_THE_INPUT_BOUNDS)
async def test_a_preview_fails_if_a_field_is_over_its_input_bound(
    api_client: ApiClient,
    items: list[InquiryItemForm],
    code: str,
) -> None:
    """A field one unit over its production bound is refused by the form itself."""
    dishonest = _preview(*items)

    response = await api_client.preview_inquiry(dishonest)

    response.assert_error(422, code)


async def test_a_preview_rejects_a_choice_outside_the_product(api_client: ApiClient) -> None:
    """A choice the product never declared is refused with ATTRIBUTE_VALUE_NOT_FOUND, as at submission."""
    form = _preview(_item(selections=[SelectionFactory.build(attribute_id=BLADE, quantity=None)]))

    response = await api_client.preview_inquiry(form)

    response.assert_error(404, "ATTRIBUTE_VALUE_NOT_FOUND")
