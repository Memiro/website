from collections.abc import Iterable, Mapping, Sequence
from decimal import ROUND_CEILING, Decimal

from memiro.entities.catalog.attribute.entity import Attribute, AttributeValue
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.measure import Dimensions
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import PricingVerdict, Quotation, QuotationLine

# The tail of the calculation rounds up to whole hundreds of roubles — the
# owner's rule, not a display convention: the number is what he is paid.
ROUNDING_STEP = Decimal(100)

type Configuration = Mapping[AttributeId, AttributeValueId]
type ResolvedValues = tuple[tuple[AttributeId, AttributeValue], ...]

_ZERO = Money(amount=Decimal(0))


def price_product(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: Configuration,
) -> Quotation:
    """Price one configuration of a product — the single implementation in the repository.

    Pure: the product, the dictionary and the settings all arrive as
    parameters, and the service never goes to the database (decision 28).
    """
    values = _values(_configuration(product, selections), attributes)
    breakdown = _breakdown(values, settings, dimensions)
    total = _round_up(_apply_min_order(_subtotal(breakdown, values), settings))
    return Quotation(verdict=PricingVerdict.PRICED, total=total, breakdown=breakdown)


def selection_deltas(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: Configuration,
) -> dict[AttributeId, Decimal]:
    """Tell what each of the customer's choices cost, against the product's own default.

    The difference is taken on exact lines, before the minimum order total
    and before rounding: on a product resting on that threshold, a difference
    of two finished totals would lie (``Quotation``, rule 4). It is signed —
    a blade cheaper than the default is a discount from the shown price.
    """
    chosen = _exact_total(product, attributes, settings, dimensions, selections)
    return {
        attribute_id: chosen.amount
        - _exact_total(
            product,
            attributes,
            settings,
            dimensions,
            {other: value for other, value in selections.items() if other != attribute_id},
        ).amount
        for attribute_id in selections
    }


def _exact_total(
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: Configuration,
) -> Money:
    """Sum the lines of a configuration with no threshold and no rounding applied."""
    values = _values(_configuration(product, selections), attributes)
    return _subtotal(_breakdown(values, settings, dimensions), values)


def _configuration(product: Product, selections: Configuration) -> Configuration:
    """Lay the customer's choices over what the owner declared for the product."""
    declared = {declared.attribute_id: declared.value_id for declared in product.declared_values}
    return declared | dict(selections)


def _breakdown(
    values: ResolvedValues,
    settings: PricingSettings,
    dimensions: Dimensions,
) -> tuple[QuotationLine, ...]:
    """Charge every paid value in the unit it is really consumed in."""
    area = dimensions.area().at_least(settings.min_area)
    quantities = {
        Unit.SQUARE_METER: area.value,
        Unit.LINEAR_METER: dimensions.perimeter().value,
        Unit.PIECE: Decimal(1),
    }
    return tuple(
        _line(attribute_id, value, quantities[value.rate.unit])
        for attribute_id, value in values
        if value.rate.unit is not Unit.FACTOR and not value.rate.is_free()
    )


def _line(attribute_id: AttributeId, value: AttributeValue, quantity: Decimal) -> QuotationLine:
    """Turn one dictionary value and its consumption into a line of the calculation."""
    return QuotationLine(
        attribute_id=attribute_id,
        value_id=value.id,
        quantity=quantity,
        rate=value.rate,
        amount=value.rate.charge(quantity),
    )


def _subtotal(breakdown: tuple[QuotationLine, ...], values: ResolvedValues) -> Money:
    """Add the lines up, the shape factor multiplying only what is cut along the contour."""
    factor = _shape_factor(values)
    scaled = {value.id for _, value in values if value.scaled_by_shape}
    plain_total = _sum(line.amount for line in breakdown if line.value_id not in scaled)
    scaled_total = _sum(line.amount for line in breakdown if line.value_id in scaled)
    return plain_total + scaled_total * factor


def _shape_factor(values: ResolvedValues) -> Decimal:
    """Multiply together every ``FACTOR`` value of the configuration."""
    factor = Decimal(1)
    for _, value in values:
        if value.rate.unit is Unit.FACTOR:
            factor *= value.rate.as_factor()
    return factor


def _values(
    configuration: Configuration,
    attributes: Sequence[Attribute],
) -> ResolvedValues:
    """Resolve the configuration into dictionary rows, in the owner's order.

    The order is the owner's and then the identifier: both sort fields default
    to zero, so a tie is the normal case and the breakdown would otherwise
    come out in a different order on every request (§8.4).
    """
    index = {attribute.id: attribute for attribute in attributes}
    resolved: list[tuple[int, int, str, AttributeId, AttributeValue]] = []
    for attribute_id, value_id in configuration.items():
        attribute = index.get(attribute_id)
        value = attribute.value(value_id) if attribute is not None else None
        if attribute is None or value is None:
            # The caller validates the configuration against the dictionary;
            # arriving here means the two disagree, which is a defect (§12.3).
            msg = f"Value {value_id} is not a row of attribute {attribute_id}"
            raise RuntimeError(msg)
        resolved.append((attribute.sort_order, value.sort_order, str(value.id), attribute_id, value))
    return tuple(
        (attribute_id, value)
        for _, _, _, attribute_id, value in sorted(resolved, key=lambda row: (row[0], row[1], row[2]))
    )


def _apply_min_order(subtotal: Money, settings: PricingSettings) -> Money:
    """Raise a total that did not reach the minimum order sum up to it."""
    return max(subtotal, settings.min_order_total)


def _round_up(total: Money) -> Money:
    """Round the total up to whole hundreds — the last operation of the calculation."""
    steps = (total.amount / ROUNDING_STEP).to_integral_value(rounding=ROUND_CEILING)
    return Money(amount=steps * ROUNDING_STEP)


def _sum(amounts: Iterable[Money]) -> Money:
    """Add up sums, keeping kopecks in full — rounding happens once, at the very end."""
    total = _ZERO
    for amount in amounts:
        total = total + amount
    return total
