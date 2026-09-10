from decimal import Decimal

import pytest

from memiro.adapters.smtp.inquiry_letter import letter_html, letter_subject
from memiro.entities.common.measure import Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.inquiry.consent import Consent
from memiro.entities.inquiry.entity import (
    ConfigurationValue,
    Inquiry,
    InquiryConfiguration,
    InquiryData,
    InquiryItemData,
    InquirySource,
    inquiry_factory,
)
from memiro.entities.inquiry.phone import Phone
from memiro.entities.pricing.quotation import PricingVerdict
from tests.clock import NOW, FakeClock
from tests.common.factory.catalog import demo_product

_MIRROR = demo_product()
_PRICE = Money(amount=Decimal(8820))
_CONFIGURATION = InquiryConfiguration(
    dimensions=Dimensions(width=Millimeters(value=800), height=Millimeters(value=600)),
    values=(ConfigurationValue(attribute_name="Рама", value_name="Алюминий", quantity=None),),
)

# Every verdict beside the words the text half prints for it (notify-manager.md,
# rule 3): the HTML card must say exactly the same.
_PRICE_LINES = [
    (PricingVerdict.PRICED, _PRICE, _CONFIGURATION, "Цена: 8 820 ₽"),
    (PricingVerdict.HIDDEN, _PRICE, _CONFIGURATION, "Цена: 8 820 ₽ (покупателю не показана)"),
    (PricingVerdict.BEYOND_LIMITS, None, _CONFIGURATION, "Цена не рассчитана: размер за пределом производства"),
    (PricingVerdict.SELECTION_NOT_PRICEABLE, None, _CONFIGURATION, "Цена не рассчитана: расчёт не взял этот выбор"),
    (PricingVerdict.NOT_PRICEABLE, None, None, "Товар без расчёта"),
]

# Russian plural forms by the last digits: one, two-to-four, the rest, and
# twenty-one falling back to the singular.
_MIRROR_COUNTS = [(1, "1 зеркало"), (2, "2 зеркала"), (5, "5 зеркал"), (21, "21 зеркало")]


def _item(
    verdict: PricingVerdict = PricingVerdict.PRICED,
    calculated_price: Money | None = _PRICE,
    configuration: InquiryConfiguration | None = _CONFIGURATION,
    wish: str = "",
) -> InquiryItemData:
    """Build one mirror snapshot straight from the combination under test."""
    return InquiryItemData(
        product_id=_MIRROR.id,
        product_name="Зеркало в раме",
        price_from=None,
        configuration=configuration,
        calculated_price=calculated_price,
        verdict=verdict,
        wish=wish,
    )


def _selection(*items: InquiryItemData, name: str = "Anna", phone: str = "+79211234567") -> Inquiry:
    """Build a saved selection inquiry at the frozen instant."""
    data = InquiryData(
        source=InquirySource.SELECTION,
        name=name,
        phone=Phone(value=phone),
        email="anna@example.test",
        comment="",
        consent=Consent(version="2026-08-31"),
        items=items,
    )
    return inquiry_factory(data, FakeClock(NOW))


def _free_form(comment: str, email: str | None = None) -> Inquiry:
    """Build a saved contact-form inquiry at the frozen instant."""
    data = InquiryData(
        source=InquirySource.FREE_FORM,
        name="Igor",
        phone=Phone(value="+79035550102"),
        email=email,
        comment=comment,
        consent=Consent(version="2026-08-31"),
        items=(),
    )
    return inquiry_factory(data, FakeClock(NOW))


@pytest.mark.parametrize(("count", "words"), _MIRROR_COUNTS)
def test_the_subject_names_the_client_and_counts_the_mirrors(count: int, words: str) -> None:
    """The subject spells the name, the dialled phone and the number of mirrors in Russian."""
    inquiry = _selection(*(_item() for _ in range(count)))

    subject = letter_subject(inquiry)

    assert subject == f"Заявка от Anna, +7 921 123-45-67 · {words}"


def test_the_subject_of_a_contact_form_inquiry_has_no_mirror_count() -> None:
    """A contact-form inquiry has no mirrors, so its subject ends after the phone."""
    inquiry = _free_form("Нужно зеркало в прихожую")

    subject = letter_subject(inquiry)

    assert subject == "Заявка от Igor, +7 903 555-01-02"


def test_a_foreign_number_is_spelled_as_a_plus_and_its_digits() -> None:
    """A number that is not a Russian eleven-digit one keeps its digits behind a single plus."""
    inquiry = _selection(_item(), phone="4915112345678")

    subject = letter_subject(inquiry)

    assert subject == "Заявка от Anna, +4915112345678 · 1 зеркало"


def test_the_date_is_spelled_in_moscow_time() -> None:
    """The saved UTC instant is shown as the studio's wall clock: three hours ahead, month in words."""
    inquiry = _selection(_item())

    html = letter_html(inquiry)

    assert "31 августа 2026, 15:34" in html


def test_a_name_with_markup_arrives_escaped() -> None:
    """Whatever the customer typed is shown as text, never rendered as markup."""
    inquiry = _selection(_item(), name="<b>Anna</b>")

    html = letter_html(inquiry)

    assert "&lt;b&gt;Anna&lt;/b&gt;" in html
    assert "<b>Anna</b>" not in html


def test_a_missing_email_is_said_without_a_link() -> None:
    """An inquiry without an email says so in words and offers no mailto link."""
    inquiry = _free_form("Нужно зеркало в прихожую")

    html = letter_html(inquiry)

    assert "не указан" in html
    assert "mailto:" not in html


def test_a_selection_is_named_as_its_source() -> None:
    """A selection inquiry names its source in words, never by the enum member."""
    inquiry = _selection(_item())

    html = letter_html(inquiry)

    assert "подборка" in html
    assert "SELECTION" not in html


def test_a_contact_form_inquiry_shows_its_comment_and_source() -> None:
    """A contact-form inquiry prints the comment as text and names the form as its source."""
    inquiry = _free_form("Звонить после 18:00 <script>")

    html = letter_html(inquiry)

    assert "Звонить после 18:00 &lt;script&gt;" in html
    assert "форма контактов" in html
    assert "FREE_FORM" not in html


@pytest.mark.parametrize(("verdict", "calculated_price", "configuration", "expected"), _PRICE_LINES)
def test_the_price_line_says_the_same_words_as_the_text_half(
    verdict: PricingVerdict,
    calculated_price: Money | None,
    configuration: InquiryConfiguration | None,
    expected: str,
) -> None:
    """Every verdict is read in the HTML card by the words the text half already prints (rule 3)."""
    inquiry = _selection(_item(verdict, calculated_price, configuration))

    html = letter_html(inquiry)

    assert expected in html
    assert verdict.value not in html


def test_a_mirror_card_lists_the_size_the_specification_and_the_wish() -> None:
    """A priced mirror prints its size, every attribute with its value and the customer's wish."""
    inquiry = _selection(_item(wish="Тёплый свет"))

    html = letter_html(inquiry)

    assert "Зеркало 1" in html
    assert "800 × 600 мм" in html
    assert "Рама" in html
    assert "Алюминий" in html
    assert "Тёплый свет" in html
