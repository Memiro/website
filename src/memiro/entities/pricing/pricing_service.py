from collections.abc import Iterable, Mapping, Sequence
from decimal import ROUND_CEILING, Decimal

from memiro.entities.catalog.attribute.entity import Attribute, AttributeKind, AttributeValue
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.catalog.product.entity import ConfiguredValue, DeclaredValue, Product
from memiro.entities.common.identifiers import AttributeId, AttributeValueId
from memiro.entities.common.measure import Dimensions
from memiro.entities.common.money import Money
from memiro.entities.pricing.pricing_settings import PricingSettings
from memiro.entities.pricing.quotation import PricingVerdict, Quotation, QuotationLine

_ZERO = Money(amount=Decimal(0))

# The tail of the calculation rounds up to whole hundreds of roubles — the
# owner's rule, not a display convention: the number is what he is paid.
ROUNDING_STEP = Decimal(100)

type Configuration = Mapping[AttributeId, ConfiguredValue]
type PricingConfiguration = Mapping[AttributeId, AttributeValueId | ConfiguredValue]
type ResolvedValues = tuple[tuple[AttributeId, AttributeValue, Decimal | None], ...]


def is_product_priceable(
    product: Product,
    attributes: Sequence[Attribute],
    selections: PricingConfiguration | None = None,
) -> bool:
    """Tell whether declarations overlaid with choices form a calculable configuration."""
    configuration, applicable = _applicable(product, attributes, selections or {})
    if any(not _has_complete_value(configuration, attribute) for attribute in applicable):
        return False
    return any(_is_paid(_resolve(attribute, configuration[attribute.id])) for attribute in applicable)


def price_product_for_customer(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: Configuration,
) -> Quotation:
    """Price a customer's question after applying the storefront gates."""
    owner_configuration_is_priceable = is_product_priceable(product, attributes)
    selected_configuration_is_priceable = is_product_priceable(product, attributes, selections)
    if not product.is_published or not owner_configuration_is_priceable or not selected_configuration_is_priceable:
        return _refusal(PricingVerdict.NOT_PRICEABLE)
    attribute_index = {attribute.id: attribute for attribute in attributes}
    if any(not attribute_index[attribute_id].is_customer_changeable for attribute_id in selections):
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
        )
    return quotation


def price_product(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: PricingConfiguration,
) -> Quotation:
    """Price one configuration of a product — the single implementation in the repository.

    Pure: the product, the dictionary and the settings all arrive as
    parameters, and the service never goes to the database (decision 28).
    """
    values = _values(_configuration_for_price(product, attributes, selections), attributes)
    breakdown = _breakdown(values, settings, dimensions)
    total = _round_up(_apply_min_order(_subtotal(breakdown, values), settings))
    return Quotation(verdict=PricingVerdict.PRICED, total=total, breakdown=breakdown)


def selection_deltas(
    *,
    product: Product,
    attributes: Sequence[Attribute],
    settings: PricingSettings,
    dimensions: Dimensions,
    selections: PricingConfiguration,
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
    selections: PricingConfiguration,
) -> Money:
    """Sum the lines of a configuration with no threshold and no rounding applied."""
    values = _values(_configuration_for_price(product, attributes, selections), attributes)
    return _subtotal(_breakdown(values, settings, dimensions), values)


def _configuration(
    product: Product,
    selections: PricingConfiguration,
) -> dict[AttributeId, ConfiguredValue]:
    """Lay the customer's choices over what the owner declared for the product."""
    declared = {
        declaration.attribute_id: ConfiguredValue(
            value_id=declaration.value_id,
            quantity=declaration.quantity,
        )
        for declaration in product.declared_values
    }
    selected = {attribute_id: _configured(value) for attribute_id, value in selections.items()}
    return declared | selected


def _configuration_for_price(
    product: Product,
    attributes: Sequence[Attribute],
    selections: PricingConfiguration,
) -> dict[AttributeId, ConfiguredValue]:
    """Keep only values whose dependency parents are present after choices are applied."""
    configuration, applicable = _applicable(product, attributes, selections)
    return {attribute.id: configuration[attribute.id] for attribute in applicable if attribute.id in configuration}


def _applicable(
    product: Product,
    attributes: Sequence[Attribute],
    selections: PricingConfiguration,
) -> tuple[dict[AttributeId, ConfiguredValue], tuple[Attribute, ...]]:
    """Resolve the customer overlay and the category attributes it makes applicable."""
    category_attributes = tuple(attribute for attribute in attributes if attribute.category_id == product.category_id)
    attribute_index = {attribute.id: attribute for attribute in category_attributes}
    configuration = _configuration(product, selections)
    applicable = tuple(
        attribute
        for attribute in category_attributes
        if _is_applicable(attribute, product, configuration, attribute_index)
    )
    return configuration, applicable


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


def _subtotal(breakdown: tuple[QuotationLine, ...], values: ResolvedValues) -> Money:
    """Add the lines up, the shape factor multiplying only what is cut along the contour."""
    factor = _shape_factor(values)
    scaled = {value.id for _, value, _ in values if value.scaled_by_shape}
    plain_total = _sum(line.amount for line in breakdown if line.value_id not in scaled)
    scaled_total = _sum(line.amount for line in breakdown if line.value_id in scaled)
    return plain_total + scaled_total * factor


def _shape_factor(values: ResolvedValues) -> Decimal:
    """Multiply together every ``FACTOR`` value of the configuration."""
    factor = Decimal(1)
    for _, value, _ in values:
        if value.rate.unit is Unit.FACTOR:
            factor *= value.rate.as_factor()
    return factor


def _values(
    configuration: Mapping[AttributeId, ConfiguredValue],
    attributes: Sequence[Attribute],
) -> ResolvedValues:
    """Resolve the configuration into dictionary rows, in the owner's order.

    The order is the owner's and then the identifier: both sort fields default
    to zero, so a tie is the normal case and the breakdown would otherwise
    come out in a different order on every request (§8.4).
    """
    index = {attribute.id: attribute for attribute in attributes}
    resolved: list[tuple[int, int, str, AttributeId, AttributeValue, Decimal | None]] = []
    for attribute_id, configured in configuration.items():
        attribute = index.get(attribute_id)
        if attribute is None:
            # The caller validates the configuration against the dictionary;
            # arriving here means the two disagree, which is a defect (§12.3).
            msg = f"Attribute {attribute_id} is not in the pricing dictionary"
            raise RuntimeError(msg)
        value = _resolve(attribute, configured)
        resolved.append(
            (
                attribute.sort_order,
                value.sort_order,
                str(value.id),
                attribute_id,
                value,
                configured.quantity if attribute.kind is AttributeKind.NUMBER else None,
            )
        )
    return tuple(
        (attribute_id, value, quantity)
        for _, _, _, attribute_id, value, quantity in sorted(
            resolved,
            key=lambda row: (row[0], row[1], row[2]),
        )
    )


def _configured(
    value: AttributeValueId | ConfiguredValue | DeclaredValue | None,
) -> ConfiguredValue:
    """Project a declaration or dictionary-row input into one domain shape."""
    if isinstance(value, ConfiguredValue):
        return value
    if isinstance(value, DeclaredValue):
        return ConfiguredValue(value_id=value.value_id, quantity=value.quantity)
    return ConfiguredValue(value_id=value, quantity=None)


def _resolve(attribute: Attribute, configured: ConfiguredValue) -> AttributeValue:
    """Resolve a select row or the sole dictionary row carrying a numeric tariff."""
    if attribute.kind is AttributeKind.NUMBER:
        if len(attribute.values) != 1 or configured.quantity is None:
            msg = f"Numeric attribute {attribute.id} needs one row and a quantity"
            raise RuntimeError(msg)
        return attribute.values[0]
    if configured.value_id is None:
        msg = f"Select attribute {attribute.id} needs a dictionary value"
        raise RuntimeError(msg)
    value = attribute.value(configured.value_id)
    if value is None:
        msg = f"Value {configured.value_id} is not a row of attribute {attribute.id}"
        raise RuntimeError(msg)
    return value


def _has_complete_value(configuration: Configuration, attribute: Attribute) -> bool:
    """Tell whether a configuration fills one applicable attribute."""
    configured = configuration.get(attribute.id)
    if configured is None:
        return False
    if attribute.kind is AttributeKind.NUMBER:
        return configured.quantity is not None
    return configured.value_id is not None


def _is_applicable(
    attribute: Attribute,
    product: Product,
    configuration: Configuration,
    attributes: Mapping[AttributeId, Attribute],
) -> bool:
    """Apply a dependent attribute when at least one configured parent is present."""
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
    return any(_configured_value_is_present(configuration, parent) for parent in parents)


def _configured_value_is_present(configuration: Configuration, attribute: Attribute) -> bool:
    """Resolve one configured parent through the dictionary's single absence rule."""
    configured = configuration.get(attribute.id)
    if configured is None or not _has_complete_value(configuration, attribute):
        return False
    return _resolve(attribute, configured).is_present()


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


def _sum(amounts: Iterable[Money]) -> Money:
    """Add up sums, keeping kopecks in full — rounding happens once, at the very end."""
    total = _ZERO
    for amount in amounts:
        total = total + amount
    return total
