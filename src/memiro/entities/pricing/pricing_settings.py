from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import PricingSettingsId
from memiro.entities.common.measure import Area, Dimensions, Millimeters
from memiro.entities.common.money import Money
from memiro.entities.errors.pricing import DuplicateSizeSurchargeError, InvalidSurchargeFactorError
from memiro_common.clock import Clock

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


def _ensure_thresholds_are_unambiguous(surcharges: Sequence[SizeSurcharge]) -> None:
    """Refuse a set in which two tiers start at the same threshold."""
    seen: set[Millimeters] = set()
    for surcharge in surcharges:
        if surcharge.from_long_side_mm in seen:
            msg = f"Duplicate size-surcharge threshold: {surcharge.from_long_side_mm.value} mm"
            raise DuplicateSizeSurchargeError(message=msg)
        seen.add(surcharge.from_long_side_mm)


@dataclass(frozen=True, slots=True)
class SizeSurchargeData:
    """Owner-controlled fields of one surcharge tier."""

    # No identifier: the set is replaced whole, and a tier is told from a tier
    # by the threshold it starts at (``pricing-settings.md``, rule 14).
    from_long_side_mm: Millimeters
    factor: Decimal


@dataclass(frozen=True, slots=True)
class ChangePricingSettingsData:
    """Owner-controlled bounds of calculation, the surcharge tiers included."""

    min_area: Area
    min_order_total: Money
    max_long_side_mm: Millimeters
    max_short_side_mm: Millimeters
    surcharges: tuple[SizeSurchargeData, ...]


@dataclass
class PricingSettings(Entity):
    """The monetary and production bounds of calculation — admin data, one row per site."""

    id: PricingSettingsId
    min_area: Area
    min_order_total: Money
    max_long_side_mm: Millimeters = field(default_factory=lambda: Millimeters(value=0))
    max_short_side_mm: Millimeters = field(default_factory=lambda: Millimeters(value=0))
    _size_surcharges: list[SizeSurcharge] = field(default_factory=list, repr=False)
    # No creation date: the row is born with the site and never a second time.
    updated_at: datetime = field(kw_only=True)

    def __post_init__(self) -> None:
        """Detach surcharge tiers and keep their thresholds unambiguous."""
        self._size_surcharges = list(self._size_surcharges)
        _ensure_thresholds_are_unambiguous(self._size_surcharges)

    def restate(self, data: "ChangePricingSettingsData", *, clock: Clock) -> None:
        """Replace the bounds of calculation together with the whole set of surcharge tiers."""
        replacement = [
            SizeSurcharge(from_long_side_mm=tier.from_long_side_mm, factor=tier.factor) for tier in data.surcharges
        ]
        _ensure_thresholds_are_unambiguous(replacement)
        self.min_area = data.min_area
        self.min_order_total = data.min_order_total
        self.max_long_side_mm = data.max_long_side_mm
        self.max_short_side_mm = data.max_short_side_mm
        # The collection is edited in place, not rebound: the ORM watches this
        # very list to learn which tiers left the set and must be deleted.
        self._size_surcharges[:] = replacement
        self.updated_at = clock.now()

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
