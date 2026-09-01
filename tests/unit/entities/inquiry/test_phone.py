import pytest

from memiro.entities.errors.inquiry import InvalidPhoneError
from memiro.entities.inquiry.phone import Phone, normalized_phone

# One entry per shape a visitor types into the form; the studio stores the
# number itself and none of the punctuation around it.
TYPED_NUMBERS = [
    ("+7 (999) 000-00-00", "+79990000000"),
    ("8 999 000 00 00", "89990000000"),
    (" +7-999-000.00.00 ", "+79990000000"),
]

# One entry per way a number stops being one the studio could dial back.
UNDIALLABLE = ["x", "", "9990000", "+7 (999) 000-00-0x", "+" + "9" * 16, "++79990000000"]


@pytest.mark.parametrize(("typed", "stored"), TYPED_NUMBERS)
def test_a_typed_number_is_stored_without_its_punctuation(typed: str, stored: str) -> None:
    """Spaces, brackets, dashes and dots are typing, not the number."""
    assert normalized_phone(typed) == Phone(value=stored)


@pytest.mark.parametrize("typed", UNDIALLABLE)
def test_a_number_the_studio_could_not_dial_is_refused(typed: str) -> None:
    """A phone that is not a phone is refused with INVALID_PHONE."""
    with pytest.raises(InvalidPhoneError, match="A phone number"):
        normalized_phone(typed)


def test_a_number_is_refused_by_the_value_itself_and_not_only_by_the_form() -> None:
    """Every road to a phone goes through the same check, hydration included."""
    with pytest.raises(InvalidPhoneError, match="A phone number"):
        Phone(value="x")
