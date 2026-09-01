from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from memiro.entities.catalog.attribute.chosen_value import ChosenValue
from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind, AttributeValue
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.catalog.product.entity import Product
from memiro.entities.common.identifiers import AttributeId
from memiro.entities.common.measure import Dimensions
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_settings import PricingSettings, SizeSurcharge
from memiro.entities.pricing.quotation import PricingVerdict, Quotation, QuotationLine

_ZERO = Money(amount=Decimal(0))

# The tail of the calculation rounds up to whole hundreds of roubles — the
# owner's rule, not a display convention: the number is what he is paid.
ROUNDING_STEP = Decimal(100)

type Selections = Mapping[AttributeId, ChosenValue]
type ResolvedValues = tuple[tuple[AttributeId, AttributeValue, Decimal | None], ...]


def is_product_priceable(
    product: Product,
    attributes: Sequence[Attribute],
    selections: Selections | None = None,
) -> bool:
    """Tell whether declarations overlaid with choices form a calculable configuration."""
    chosen_values, applicable = _applicable(product, attributes, selections or {})
    if any(not _has_complete_value(chosen_values, attribute) for attribute in applicable):
        return False
    return any(_is_paid(_resolve(attribute, chosen_values[attribute.id])) for attribute in applicable)


def price_product_for_customer(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: Selections,
) -> Quotation:
    """Price a customer's question after applying the storefront gates."""
    owner_configuration_is_priceable = is_product_priceable(product, attributes)
    selected_configuration_is_priceable = is_product_priceable(product, attributes, selections)
    if not product.is_published or not owner_configuration_is_priceable or not selected_configuration_is_priceable:
        return _refusal(PricingVerdict.NOT_PRICEABLE)
    attribute_index = {attribute.id: attribute for attribute in attributes}
    # A selection naming an attribute outside the dictionary is a refusal, not
    # a defect: the gate above tolerates the stranger by dropping it, so this
    # line must not be the one that decides it was a crash.
    chosen = [attribute_index.get(attribute_id) for attribute_id in selections]
    if any(attribute is None or not attribute.is_customer_changeable for attribute in chosen):
        return _refusal(PricingVerdict.NOT_PRICEABLE)
    if not settings.is_within_limits(dimensions):
        return _refusal(PricingVerdict.BEYOND_LIMITS)
    quotation = price_product(
        product=product,
        attributes=attributes,
        settings=settings,
        dimensions=dimensions,
        selections=selections,
    )
    if product.hides_calculated_price:
        return Quotation(
            verdict=PricingVerdict.HIDDEN,
            total=quotation.total,
            breakdown=quotation.breakdown,
            size_surcharge_from_long_side_mm=quotation.size_surcharge_from_long_side_mm,
        )
    return quotation


def price_product(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: Selections,
) -> Quotation:
    """Price one configuration of a product — the single implementation in the repository.

    Pure: the product, the dictionary and the settings all arrive as
    parameters, and the service never goes to the database (decision 28).
    """
    values = _values(_applicable_values(product, attributes, selections), attributes)
    breakdown = _breakdown(values, settings, dimensions)
    size_surcharge = settings.size_surcharge_for(dimensions)
    total = _round_up(_apply_min_order(_subtotal(breakdown, values, size_surcharge), settings))
    return Quotation(
        verdict=PricingVerdict.PRICED,
        total=total,
        breakdown=breakdown,
        size_surcharge_from_long_side_mm=(size_surcharge.from_long_side_mm if size_surcharge is not None else None),
    )


def selection_deltas(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: Selections,
) -> dict[AttributeId, Decimal]:
    """Tell what each of the customer's choices cost, against the product's own default.

    The difference is taken on exact lines, before the minimum order total
    and before rounding: on a product resting on that threshold, a difference
    of two finished totals would lie (``Quotation``, rule 4). It is signed —
    a blade cheaper than the default is a discount from the shown price.
    """
    chosen = _exact_total(product, attributes, settings, dimensions, selections)
    applicable_ids = {attribute.id for attribute in _applicable(product, attributes, selections)[1]}
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
        if attribute_id in applicable_ids
    }


def _exact_total(
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: Selections,
) -> Money:
    """Sum the lines of a configuration with no threshold and no rounding applied."""
    values = _values(_applicable_values(product, attributes, selections), attributes)
    return _subtotal(
        _breakdown(values, settings, dimensions),
        values,
        settings.size_surcharge_for(dimensions),
    )


def _overlay(
    product: Product,
    selections: Selections,
) -> dict[AttributeId, ChosenValue]:
    """Lay the customer's choices over what the owner declared for the product."""
    declared = {declaration.attribute_id: declaration.chosen for declaration in product.declared_values}
    return declared | dict(selections)


def _applicable_values(
    product: Product,
    attributes: Sequence[Attribute],
    selections: Selections,
) -> dict[AttributeId, ChosenValue]:
    """Keep only values whose dependency parents are present after choices are applied."""
    chosen_values, applicable = _applicable(product, attributes, selections)
    return {attribute.id: chosen_values[attribute.id] for attribute in applicable if attribute.id in chosen_values}


def _applicable(
    product: Product,
    attributes: Sequence[Attribute],
    selections: Selections,
) -> tuple[dict[AttributeId, ChosenValue], tuple[Attribute, ...]]:
    """Resolve the customer overlay and the category attributes it makes applicable."""
    category_attributes = tuple(attribute for attribute in attributes if attribute.category_id == product.category_id)
    attribute_index = {attribute.id: attribute for attribute in category_attributes}
    chosen_values = _overlay(product, selections)
    applicable = tuple(
        attribute
        for attribute in category_attributes
        if _is_applicable(attribute, product, chosen_values, attribute_index)
    )
    return chosen_values, applicable


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
        _line(
            attribute_id,
            value,
            quantity if quantity is not None else quantities[value.rate.unit],
        )
        for attribute_id, value, quantity in values
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


def _subtotal(
    breakdown: tuple[QuotationLine, ...],
    values: ResolvedValues,
    size_surcharge: SizeSurcharge | None,
) -> Money:
    """Add the lines, multiplying each only by the independent factors marking it."""
    shape_factor = _shape_factor(values)
    size_factor = size_surcharge.factor if size_surcharge is not None else Decimal(1)
    scaled_by_shape = {value.id for _, value, _ in values if value.scaled_by_shape}
    scaled_by_size = {value.id for _, value, _ in values if value.scaled_by_size_surcharge}
    total = _ZERO
    for line in breakdown:
        factor = Decimal(1)
        if line.value_id in scaled_by_shape:
            factor *= shape_factor
        if line.value_id in scaled_by_size:
            factor *= size_factor
        total = total + line.amount * factor
    return total


def _shape_factor(values: ResolvedValues) -> Decimal:
    """Multiply together every ``FACTOR`` value of the configuration."""
    factor = Decimal(1)
    for _, value, _ in values:
        if value.rate.unit is Unit.FACTOR:
            factor *= value.rate.as_factor()
    return factor


def _values(
    chosen_values: Selections,
    attributes: Sequence[Attribute],
) -> ResolvedValues:
    """Resolve the chosen values into dictionary rows, in the owner's order.

    The order is the owner's and then the identifier: both sort fields default
    to zero, so a tie is the normal case and the breakdown would otherwise
    come out in a different order on every request (§8.4).
    """
    index = {attribute.id: attribute for attribute in attributes}
    resolved: list[_ResolvedValue] = []
    for attribute_id, chosen in chosen_values.items():
        attribute = index.get(attribute_id)
        if attribute is None:
            # The caller validates the choices against the dictionary;
            # arriving here means the two disagree, which is a defect (§12.3).
            msg = f"Attribute {attribute_id} is not in the pricing dictionary"
            raise RuntimeError(msg)
        value = _resolve(attribute, chosen)
        resolved.append(
            _ResolvedValue(
                attribute=attribute,
                value=value,
                quantity=chosen.quantity if attribute.kind is AttributeKind.NUMBER else None,
            )
        )
    return tuple((row.attribute.id, row.value, row.quantity) for row in sorted(resolved, key=_owner_order))


@dataclass(frozen=True, slots=True)
class _ResolvedValue:
    """One chosen value paired with the attribute it belongs to and its consumption."""

    attribute: Attribute
    value: AttributeValue
    quantity: Decimal | None


def _owner_order(row: _ResolvedValue) -> tuple[int, int, str]:
    """Order one resolved row by the owner's two sort fields, breaking a tie by identifier."""
    return (row.attribute.sort_order, row.value.sort_order, str(row.value.id))


def _resolve(attribute: Attribute, chosen: ChosenValue) -> AttributeValue:
    """Resolve one chosen value into the dictionary row that carries its tariff."""
    value = attribute.row_of(chosen)
    if value is None:
        # The caller validates every choice against the dictionary through the
        # same domain method; arriving here means it did not (§12.3).
        msg = f"Value {chosen} is not a legal value of attribute {attribute.id}"
        raise RuntimeError(msg)
    return value


def _has_complete_value(chosen_values: Selections, attribute: Attribute) -> bool:
    """Tell whether the chosen values fill one applicable attribute."""
    chosen = chosen_values.get(attribute.id)
    if chosen is None:
        return False
    if attribute.kind is AttributeKind.NUMBER:
        return chosen.quantity is not None
    return chosen.value_id is not None


def _is_applicable(
    attribute: Attribute,
    product: Product,
    chosen_values: Selections,
    attributes: Mapping[AttributeId, Attribute],
) -> bool:
    """Apply a dependent attribute when at least one chosen parent is present."""
    if not attribute.parent_ids:
        return True
    parents: list[Attribute] = []
    for parent_id in attribute.parent_ids:
        parent = attributes.get(parent_id)
        if parent is None:
            msg = (
                f"Parent attribute {parent_id} of attribute {attribute.id} "
                f"is missing or outside product category {product.category_id}"
            )
            raise RuntimeError(msg)
        parents.append(parent)
    return any(_chosen_value_is_present(chosen_values, parent) for parent in parents)


def _chosen_value_is_present(chosen_values: Selections, attribute: Attribute) -> bool:
    """Resolve one chosen parent through the dictionary's single absence rule."""
    chosen = chosen_values.get(attribute.id)
    if chosen is None or not _has_complete_value(chosen_values, attribute):
        return False
    return _resolve(attribute, chosen).is_present()


def _is_paid(value: AttributeValue) -> bool:
    """Tell whether a row contributes money rather than only describing or scaling."""
    return value.rate.unit is not Unit.FACTOR and not value.rate.is_free()


def _refusal(verdict: PricingVerdict) -> Quotation:
    """Build a customer gate result carrying neither arithmetic nor lines."""
    return Quotation(verdict=verdict, total=None, breakdown=())


def _apply_min_order(subtotal: Money, settings: PricingSettings) -> Money:
    """Raise a total that did not reach the minimum order sum up to it."""
    return max(subtotal, settings.min_order_total)


def _round_up(total: Money) -> Money:
    """Round the total up to whole hundreds — the last operation of the calculation."""
    steps = (total.amount / ROUNDING_STEP).to_integral_value(rounding=ROUND_CEILING)
    return Money(amount=steps * ROUNDING_STEP)
