from dataclasses import dataclass
from uuid import UUID

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import PricingSettingsId
from memiro.entities.common.measure import Area
from memiro.entities.common.money import Money

# The site has exactly one row of settings, and it is fetched by this id
# rather than by "whatever the table holds": a stray second row must not be
# able to price the catalogue.
PRICING_SETTINGS_ID = PricingSettingsId(UUID("0197c0de-0000-7000-8000-000000000001"))


@dataclass
class PricingSettings(Entity):
    """The bounds the calculation lives in — admin data, one row per site.

    Aggregate root with a known id. The production limit and the size
    surcharge steps arrive with their own tickets; this slice holds the two
    lower bounds the calculation cannot do without.
    """

    id: PricingSettingsId
    min_area: Area
    min_order_total: Money
