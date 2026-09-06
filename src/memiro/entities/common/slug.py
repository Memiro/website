"""Transliteration of a name into a public address, so the owner need not type one (§6.2)."""

import re
import unicodedata

# One table, Cyrillic to the letters a URL is written in. It is the domain's
# own because the address is the domain's: a library would bring a second
# spelling of the same names with the next version bump.
CYRILLIC: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

_SEPARATORS = re.compile(r"[^a-z0-9]+")

# One letter of a name can unfold into four ("щ" is "shch"), so an address is
# bounded on its own and not by the length of the name it came from.
MAX_SLUG_LENGTH = 255


def slugify(name: str) -> str:
    """Turn a name into a lowercase latin address, or into nothing when it holds no letter."""
    transliterated = "".join(CYRILLIC.get(character, character) for character in name.casefold())
    # An accent is dropped rather than separated on: "é" is the letter "e"
    # wearing a mark the address cannot carry, not two words. Everything else
    # the address cannot spell becomes a separator, digits included in words.
    decomposed = unicodedata.normalize("NFKD", transliterated)
    folded = "".join(character for character in decomposed if not unicodedata.combining(character))
    address = _SEPARATORS.sub("-", folded).strip("-")
    return address[:MAX_SLUG_LENGTH].rstrip("-")
