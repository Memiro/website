import pytest

from memiro.application.common.input_limits import MAX_NAME_LENGTH
from memiro.entities.common.slug import MAX_SLUG_LENGTH, slugify

TRANSLITERATIONS = [
    ("Зеркало в раме", "zerkalo-v-rame"),
    ("Щётка ёлки", "shchetka-elki"),
    ("Объём и подъезд", "obem-i-podezd"),
    ("Зеркало 800×600", "zerkalo-800-600"),
    ("  Двойной  --  дефис  ", "dvoynoy-defis"),
    ("Mirror LED", "mirror-led"),
]


@pytest.mark.parametrize(("name", "expected"), TRANSLITERATIONS)
def test_a_name_becomes_a_public_address(name: str, expected: str) -> None:
    """A name of any script becomes lowercase latin words joined by single hyphens."""
    assert slugify(name) == expected


def test_a_name_of_nothing_but_punctuation_yields_no_address() -> None:
    """A name carrying no letter and no digit leaves the address empty."""
    assert slugify("!!! ??? ...") == ""


def test_a_name_of_letters_that_unfold_yields_an_address_the_column_holds() -> None:
    """A name whose every letter unfolds into four is still addressed within the address bound."""
    assert len(slugify("щ" * MAX_NAME_LENGTH)) == MAX_SLUG_LENGTH


def test_a_truncated_address_does_not_end_on_a_separator() -> None:
    """An address cut at the bound keeps the shape of an address: words joined by single hyphens."""
    assert not slugify("щи " * MAX_NAME_LENGTH).endswith("-")
