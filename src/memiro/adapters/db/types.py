from decimal import Decimal
from typing import override

from sqlalchemy import Dialect, Numeric
from sqlalchemy.types import TypeDecorator

from memiro.entities.common.measure import Area
from memiro.entities.common.money import Money

# Money is stored to the kopeck; the area of a mirror to the fourth decimal —
# a square millimetre. Both deserialize through the domain constructor, so a
# corrupted row never loads silently (§8.5).
_MONEY = Numeric(12, 2)
_AREA = Numeric(10, 4)


class MoneyType(TypeDecorator[Money]):
    """Column type storing ``Money`` as a fixed-point number of roubles."""

    impl = _MONEY
    cache_ok = True

    @override
    def process_bind_param(self, value: Money | None, dialect: Dialect) -> Decimal | None:
        """Flatten the sum into the column."""
        return None if value is None else value.amount

    @override
    def process_result_value(self, value: Decimal | None, dialect: Dialect) -> Money | None:
        """Rebuild the sum through the domain constructor."""
        return None if value is None else Money(amount=value)


class AreaType(TypeDecorator[Area]):
    """Column type storing ``Area`` as a fixed-point number of square metres."""

    impl = _AREA
    cache_ok = True

    @override
    def process_bind_param(self, value: Area | None, dialect: Dialect) -> Decimal | None:
        """Flatten the area into the column."""
        return None if value is None else value.value

    @override
    def process_result_value(self, value: Decimal | None, dialect: Dialect) -> Area | None:
        """Rebuild the area through the domain constructor."""
        return None if value is None else Area(value=value)
