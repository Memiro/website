import pytest

from memiro.entities.errors.inquiry import ConsentRequiredError, EmptyInquiryError
from memiro.entities.inquiry.entity import InquiryData, InquirySource, inquiry_factory
from tests.clock import NOW, FakeClock


def _data(*, consent: bool = True) -> InquiryData:
    """Build a selection request whose fields the test does not otherwise care about."""
    return InquiryData(
        source=InquirySource.SELECTION,
        name="Anna",
        phone="+79990000000",
        email=None,
        comment="",
        consent=consent,
        consent_version="2026-08-31",
        items=(),
    )


def test_a_selection_without_items_is_rejected() -> None:
    """An empty selection is rejected with EMPTY_INQUIRY."""
    with pytest.raises(EmptyInquiryError, match="A selection inquiry needs at least one item"):
        inquiry_factory(_data(), FakeClock(NOW))


def test_an_inquiry_without_consent_is_rejected() -> None:
    """A missing consent is rejected with CONSENT_REQUIRED."""
    with pytest.raises(ConsentRequiredError, match="Consent is required"):
        inquiry_factory(_data(consent=False), FakeClock(NOW))
