import re
from dataclasses import dataclass

from memiro.entities.errors.inquiry import InvalidPhoneError

# The digits of a national number at their shortest and of an E.164 number at
# its longest: the studio dials the number itself, and country prefixes vary.
MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 15

_NUMBER = re.compile(rf"\+?\d{{{MIN_PHONE_DIGITS},{MAX_PHONE_DIGITS}}}")
_TYPING = re.compile(r"[\s()\-.]")


@dataclass(frozen=True, slots=True)
class Phone:
    """A telephone number in the one shape the studio stores and dials back."""

    value: str

    def __post_init__(self) -> None:
        """Refuse a number the studio could not call back — including one hydrated from a row."""
        if not _NUMBER.fullmatch(self.value):
            raise InvalidPhoneError


def normalized_phone(raw: str) -> Phone:
    """Drop the punctuation a visitor types around the number and keep the number."""
    return Phone(value=_TYPING.sub("", raw))
