from dataclasses import dataclass
from decimal import Decimal

from memiro.entities.errors.measure import EmptyDimensionsError, NegativeMeasureError

# Millimetres are integers, metres are fractional; this is the only bridge
# between them, and it lives here so no second conversion appears elsewhere.
MILLIMETERS_IN_METER = Decimal(1000)


@dataclass(frozen=True, slots=True, order=True)
class Millimeters:
    """A linear size in millimetres — the unit the customer types in."""

    value: int

    def __post_init__(self) -> None:
        """Reject a negative size; zero is legal and means nothing by itself."""
        if self.value < 0:
            msg = f"Millimeters cannot be negative: {self.value}"
            raise NegativeMeasureError(message=msg)

    def to_meters(self) -> Decimal:
        """Convert to metres — the single door out of millimetres."""
        return Decimal(self.value) / MILLIMETERS_IN_METER


@dataclass(frozen=True, slots=True, order=True)
class Area:
    """A surface in square metres — the consumption of everything cut from a sheet."""

    value: Decimal

    def __post_init__(self) -> None:
        """Reject a negative area."""
        if self.value < 0:
            msg = f"Area cannot be negative: {self.value}"
            raise NegativeMeasureError(message=msg)

    def at_least(self, minimum: "Area") -> "Area":
        """Raise the area up to the minimum billable one; cutting a sheet gets no cheaper."""
        return max(self, minimum)


@dataclass(frozen=True, slots=True, order=True)
class Perimeter:
    """A rim length in linear metres — the consumption of everything running along the edge."""

    value: Decimal

    def __post_init__(self) -> None:
        """Reject a negative perimeter."""
        if self.value < 0:
            msg = f"Perimeter cannot be negative: {self.value}"
            raise NegativeMeasureError(message=msg)


@dataclass(frozen=True, slots=True)
class Dimensions:
    """The pair of sides of a product, kept exactly as they were entered."""

    width: Millimeters
    height: Millimeters

    def __post_init__(self) -> None:
        """Reject a side of zero: a product with no side does not exist."""
        if self.width.value <= 0 or self.height.value <= 0:
            msg = f"Dimensions must be positive: {self.width.value} x {self.height.value}"
            raise EmptyDimensionsError(message=msg)

    @property
    def long_side(self) -> Millimeters:
        """Return the longer side: the product is turned, and rules speak of sides, not fields."""
        return max(self.width, self.height)

    @property
    def short_side(self) -> Millimeters:
        """Return the shorter side."""
        return min(self.width, self.height)

    def area(self) -> Area:
        """Return the area — the only place millimetres become square metres."""
        return Area(value=self.width.to_meters() * self.height.to_meters())

    def perimeter(self) -> Perimeter:
        """Return the perimeter: two times width plus height."""
        return Perimeter(value=2 * (self.width.to_meters() + self.height.to_meters()))
