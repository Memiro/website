from dataclasses import dataclass, field
from uuid import UUID

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import PricingSettingsId
from memiro.entities.common.measure import Area, Dimensions, Millimeters
from memiro.entities.common.money import Money

# The site has exactly one row of settings, and it is fetched by this id
# rather than by "whatever the table holds": a stray second row must not be
# able to price the catalogue.
PRICING_SETTINGS_ID: PricingSettingsId = UUID("0197c0de-0000-7000-8000-000000000001")


@dataclass
class PricingSettings(Entity):
    """The monetary and production bounds of calculation — admin data, one row per site."""

    id: PricingSettingsId
    min_area: Area
    min_order_total: Money
    max_long_side_mm: Millimeters = field(default_factory=lambda: Millimeters(value=0))
    max_short_side_mm: Millimeters = field(default_factory=lambda: Millimeters(value=0))

    def is_within_limits(self, dimensions: Dimensions) -> bool:
        """Tell whether a rotated product fits the production bounds."""
        return self.max_long_side_mm.allows(dimensions.long_side) and self.max_short_side_mm.allows(
            dimensions.short_side
        )
