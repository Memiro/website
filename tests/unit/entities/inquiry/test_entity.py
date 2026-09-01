from decimal import Decimal
from uuid import uuid4

import pytest

from memiro.entities.common.identifiers import InquiryItemId, ProductId
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.inquiry import EmptyInquiryError
from memiro.entities.inquiry.consent import Consent
from memiro.entities.inquiry.entity import (
    InquiryConfiguration,
    InquiryData,
    InquiryItem,
    InquiryItemData,
    InquirySource,
    inquiry_factory,
)
from memiro.entities.inquiry.phone import Phone
from memiro.entities.pricing.quotation import PricingVerdict
from tests.clock import NOW, FakeClock
from tests.common.factory.catalog import demo_product

_MIRROR = demo_product()
_PRODUCT: ProductId = _MIRROR.id
_PRICE = Money(amount=Decimal(8900))
_CONFIGURATION = InquiryConfiguration(
    dimensions=Dimensions(width=Millimeters(value=800), height=Millimeters(value=600)),
    values=(),
)


def _data() -> InquiryData:
    """Build a selection request whose fields the test does not otherwise care about."""
    return InquiryData(
        source=InquirySource.SELECTION,
        name="Anna",
        phone=Phone(value="+79990000000"),
        email=None,
        comment="",
        consent=Consent(version="2026-08-31"),
        items=(),
    )


def _snapshot(
    verdict: PricingVerdict,
    calculated_price: Money | None,
    configuration: InquiryConfiguration | None,
) -> InquiryItemData:
    """Build one item snapshot straight from the combination under test."""
    return InquiryItemData(
        product_id=_PRODUCT,
        product_name="Зеркало в раме",
        price_from=None,
        configuration=configuration,
        calculated_price=calculated_price,
        verdict=verdict,
        wish="",
    )


def _item(
    verdict: PricingVerdict,
    calculated_price: Money | None,
    configuration: InquiryConfiguration | None,
) -> InquiryItem:
    """Hydrate one stored item snapshot from the combination under test."""
    item_id: InquiryItemId = uuid4()
    return InquiryItem(
        id=item_id,
        product_id=_PRODUCT,
        product_name="Зеркало в раме",
        price_from=None,
        configuration=configuration,
        calculated_price=calculated_price,
        verdict=verdict,
        wish="",
    )


def test_a_selection_without_items_is_rejected() -> None:
    """An empty selection is rejected with EMPTY_INQUIRY."""
    with pytest.raises(EmptyInquiryError, match="A selection inquiry needs at least one item"):
        inquiry_factory(_data(), FakeClock(NOW))


def test_a_priced_snapshot_keeps_the_price_and_the_configuration_it_was_shown() -> None:
    """PRICED means the manager reads both what was configured and what it cost."""
    snapshot = _snapshot(PricingVerdict.PRICED, _PRICE, _CONFIGURATION)

    assert snapshot.calculated_price == _PRICE
    assert snapshot.configuration == _CONFIGURATION


def test_a_hidden_snapshot_keeps_the_price_the_storefront_was_not_told() -> None:
    """HIDDEN priced the mirror, so the manager reads the price the customer never saw (ADR-0008)."""
    snapshot = _snapshot(PricingVerdict.HIDDEN, _PRICE, _CONFIGURATION)

    assert snapshot.calculated_price == _PRICE
    assert snapshot.configuration == _CONFIGURATION


def test_a_hidden_snapshot_without_a_price_is_a_defect() -> None:
    """A verdict that priced the mirror cannot arrive without the price."""
    with pytest.raises(RuntimeError, match="disagrees with the presence of a price"):
        _snapshot(PricingVerdict.HIDDEN, None, _CONFIGURATION)


def test_a_beyond_limits_snapshot_keeps_the_configuration_without_a_price() -> None:
    """A size beyond production keeps the customer's configuration and names no price."""
    snapshot = _snapshot(PricingVerdict.BEYOND_LIMITS, None, _CONFIGURATION)

    assert snapshot.calculated_price is None
    assert snapshot.configuration == _CONFIGURATION


def test_a_priced_snapshot_without_a_price_is_a_defect() -> None:
    """A verdict disagreeing with the presence of a price cannot happen and leaves as a 500."""
    with pytest.raises(RuntimeError, match="disagrees with the presence of a price"):
        _snapshot(PricingVerdict.PRICED, None, _CONFIGURATION)


def test_a_refusing_snapshot_with_a_price_is_a_defect() -> None:
    """A refusal that named no price cannot carry one."""
    with pytest.raises(RuntimeError, match="disagrees with the presence of a price"):
        _snapshot(PricingVerdict.BEYOND_LIMITS, _PRICE, _CONFIGURATION)


def test_a_not_priceable_snapshot_carries_no_configuration() -> None:
    """A product outside the calculated set gives the customer nothing to configure."""
    with pytest.raises(RuntimeError, match="disagrees with the presence of a configuration"):
        _snapshot(PricingVerdict.NOT_PRICEABLE, None, _CONFIGURATION)


def test_a_configured_snapshot_cannot_lose_its_configuration() -> None:
    """A verdict that priced or refused a configuration must keep it."""
    with pytest.raises(RuntimeError, match="disagrees with the presence of a configuration"):
        _snapshot(PricingVerdict.BEYOND_LIMITS, None, None)


def test_an_item_with_an_impossible_combination_cannot_be_built() -> None:
    """The stored position holds the same invariant as the data it was made from.

    The row coming back from the database is the pair in
    ``tests/integration/submit_inquiry/test_inquiry_hydration.py`` (§14.4.3).
    """
    with pytest.raises(RuntimeError, match="disagrees with the presence of a price"):
        _item(PricingVerdict.BEYOND_LIMITS, _PRICE, _CONFIGURATION)
