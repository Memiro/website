"""Hand-checked pricing expectations shared by focused domain-service tests."""

from decimal import Decimal

from memiro.entities.catalog.attribute.rate import Rate, Unit
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.money import Money
from memiro.entities.pricing.quotation import PricingVerdict, Quotation, QuotationLine
from tests.common.factory.catalog import ALUMINIUM, BLADE, FRAME, MOUNT, SILVER, WITH_MOUNT


def quotation_line(
    attribute_id: AttributeId,
    value_id: AttributeValueId,
    quantity: str,
    price: tuple[str, Unit, str],
) -> QuotationLine:
    """Build one line from independently checked literal numbers."""
    rate, unit, amount = price
    return QuotationLine(
        attribute_id=attribute_id,
        value_id=value_id,
        quantity=Decimal(quantity),
        rate=Rate(amount=Money(amount=Decimal(rate)), unit=unit),
        amount=Money(amount=Decimal(amount)),
    )


def canonical_quotation(verdict: PricingVerdict) -> Quotation:
    """Build the hand-checked workbook result without calling pricing logic."""
    return Quotation(
        verdict=verdict,
        total=Money(amount=Decimal(8900)),
        breakdown=(
            quotation_line(BLADE, SILVER, "0.48", ("4500", Unit.SQUARE_METER, "2160")),
            quotation_line(FRAME, ALUMINIUM, "2.8", ("2200", Unit.LINEAR_METER, "6160")),
            quotation_line(MOUNT, WITH_MOUNT, "1", ("500", Unit.PIECE, "500")),
        ),
    )
