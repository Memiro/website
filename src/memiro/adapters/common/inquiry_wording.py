"""The manager's reading of an inquiry snapshot — the email and the admin say the same words."""

from memiro.entities.common.measure import Dimensions
from memiro.entities.common.money import Money
from memiro.entities.inquiry.entity import ConfigurationValue
from memiro.entities.pricing.quotation import PricingVerdict

_UNPRICED_WORDS = {
    PricingVerdict.BEYOND_LIMITS: "Цена не рассчитана: размер за пределом производства",
    PricingVerdict.SELECTION_NOT_PRICEABLE: "Цена не рассчитана: расчёт не взял этот выбор",
    PricingVerdict.NOT_PRICEABLE: "Товар без расчёта",
}


def money_words(value: Money) -> str:
    """Spell a sum the way the owner writes prices: whole roubles, thousands apart."""
    amount = value.amount
    text = f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,.2f}"
    return text.replace(",", " ") + " ₽"


def price_words(verdict: PricingVerdict, calculated_price: Money | None) -> str:
    """Say what the calculation did with the position, so the manager never reads a verdict code (rule 19)."""
    if calculated_price is None:
        words = _UNPRICED_WORDS.get(verdict)
        if words is None:
            msg = f"Verdict {verdict} priced the position, yet the snapshot holds no price"
            raise RuntimeError(msg)
        return words
    if verdict is PricingVerdict.HIDDEN:
        # Without the remark the manager would name a number the customer
        # has never seen as one already agreed on.
        return f"Цена: {money_words(calculated_price)} (покупателю не показана)"
    return f"Цена: {money_words(calculated_price)}"


def size_words(dimensions: Dimensions) -> str:
    """Spell the size in the millimetres the customer typed."""
    return f"{dimensions.width.value} × {dimensions.height.value} мм"  # noqa: RUF001  # the multiplication sign is the typographic one


def specification_words(value: ConfigurationValue) -> tuple[str, str]:
    """Spell one value of the specification as the attribute and its value, a count standing in for a row."""
    if value.quantity is not None:
        # The database keeps the count in its own scale ("2.5000"); the
        # customer typed "2.5" and the manager reads it back the same way.
        return value.attribute_name, f"{value.quantity.normalize():f}"
    return value.attribute_name, str(value.value_name)


def specification_line(value: ConfigurationValue) -> str:
    """Spell one value of the specification as "attribute: value"."""
    attribute, words = specification_words(value)
    return f"{attribute}: {words}"
