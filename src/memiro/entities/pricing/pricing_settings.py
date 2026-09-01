from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import PricingSettingsId
from memiro.entities.common.measure import Area, Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.pricing import DuplicateSizeSurchargeError, InvalidSurchargeFactorError

# The site has exactly one row of settings, and it is fetched by this id
# rather than by "whatever the table holds": a stray second row must not be
# able to price the catalogue.
PRICING_SETTINGS_ID: PricingSettingsId = UUID("0197c0de-0000-7000-8000-000000000001")


@dataclass
class SizeSurcharge(Entity):
    """One step after which a large product becomes dearer."""

    from_long_side_mm: Millimeters
    factor: Decimal

    def __post_init__(self) -> None:
        """Require the factor to express a surcharge rather than a second off switch."""
        if self.factor <= 1:
            msg = f"Invalid size-surcharge factor: {self.factor}"
            raise InvalidSurchargeFactorError(message=msg)


@dataclass
class PricingSettings(Entity):
    """The monetary and production bounds of calculation — admin data, one row per site."""

    id: PricingSettingsId
    min_area: Area
    min_order_total: Money
    max_long_side_mm: Millimeters = field(default_factory=lambda: Millimeters(value=0))
    max_short_side_mm: Millimeters = field(default_factory=lambda: Millimeters(value=0))
    _size_surcharges: list[SizeSurcharge] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        """Detach surcharge tiers and keep their thresholds unambiguous."""
        self._size_surcharges = list(self._size_surcharges)
        seen: set[Millimeters] = set()
        for surcharge in self._size_surcharges:
            if surcharge.from_long_side_mm in seen:
                msg = f"Duplicate size-surcharge threshold: {surcharge.from_long_side_mm.value} mm"
                raise DuplicateSizeSurchargeError(message=msg)
            seen.add(surcharge.from_long_side_mm)

    @property
    def size_surcharges(self) -> tuple[SizeSurcharge, ...]:
        """Expose surcharge tiers without handing out the aggregate's mutable collection."""
        return tuple(self._size_surcharges)

    def is_within_limits(self, dimensions: Dimensions) -> bool:
        """Tell whether a rotated product fits the production bounds."""
        return self.max_long_side_mm.allows(dimensions.long_side) and self.max_short_side_mm.allows(
            dimensions.short_side
        )

    def size_surcharge_for(self, dimensions: Dimensions) -> SizeSurcharge | None:
        """Return the highest tier reached by the product's rotated long side."""
        applicable = (
            surcharge for surcharge in self.size_surcharges if surcharge.from_long_side_mm <= dimensions.long_side
        )
        return max(applicable, key=lambda surcharge: surcharge.from_long_side_mm, default=None)
