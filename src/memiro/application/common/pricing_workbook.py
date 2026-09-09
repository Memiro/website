from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

from memiro.entities.catalog.attribute.entity import Attribute
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.measure import Dimensions
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import Quotation


@dataclass(frozen=True, slots=True)
class CheckedSize:
    """One size of the check sheet, priced by the engine or refused by it."""

    dimensions: Dimensions
    quotation: Quotation | None


@dataclass(frozen=True, slots=True)
class PricingWorkbookSource:
    """Everything the workbook shows: the dictionary, the bounds, the defaults and the engine's own totals."""

    attributes: tuple[Attribute, ...]
    settings: PricingSettings
    product: Product | None
    checks: tuple[CheckedSize, ...]


class PricingWorkbookRenderer(Protocol):
    """Port turning the live pricing data into a workbook the owner opens in a spreadsheet."""

    @abstractmethod
    def render(self, source: PricingWorkbookSource) -> bytes:
        """Build the workbook and return it as the bytes of a file."""
        raise NotImplementedError
