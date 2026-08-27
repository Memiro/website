from dataclasses import dataclass

from memiro.entities.common.entity import Entity
from memiro.entities.common.identifiers import PricingSettingsId
from memiro.entities.common.measure import Area
from memiro.entities.common.money import Money


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
