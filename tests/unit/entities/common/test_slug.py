import pytest

from memiro.entities.common.slug import slugify

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
