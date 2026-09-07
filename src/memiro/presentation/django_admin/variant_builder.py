# django-stubs types every model field as a generic descriptor, and only its
# mypy plugin solves the parameters; basedpyright sees `Unknown` on each column
# the panel reads a declaration through.
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
"""The panel under the product card: what it shows, what it sends and what it answers (ADR-0011).

The panel is the owner's own question about a price and his own commands over
the variants; it is not part of the card's form, and every one of its three
views answers JSON. A refusal is that JSON's ``error`` — there is no form to
come back to.
"""

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import structlog
from dishka import AsyncContainer
from django.http import HttpRequest, JsonResponse, QueryDict
from pydantic import ValidationError

from memiro.application.common.input_limits import MAX_QUANTITY, MAX_SIDE_MM
from memiro.application.manage_products import (
    AddVariant,
    AddVariantForm,
    ChangeVariant,
    ChangeVariantForm,
    DuplicateVariantWithSize,
    DuplicateVariantWithSizeForm,
    ListVariants,
    QuotedVariant,
    QuoteVariant,
    QuoteVariantForm,
    RemoveVariant,
    VariantModel,
    VariantOverrideModel,
    VariantsList,
)
from memiro.application.manage_products.shared import VariantOverrideForm
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.common.identifiers import ProductId, VariantId
from memiro.presentation.django_admin.bridge import bridge
from memiro.presentation.django_admin.refusals import refusal_text
from memiro_common.errors import AppError
from memiro_common.logger import Logger

# The names the panel posts its own fields under. They are not the names of the
# card: the panel has no fields with a ``name`` at all, and the script spells
# these out itself when it sends a request.
WIDTH = "width_mm"
HEIGHT = "height_mm"
ORDER = "sort_order"
VALUE = "value"
QUANTITY = "quantity"
VARIANT = "variant"
DUPLICATE = "duplicate"

# What the panel says in the owner's language: the machine code is not a
# message (§12.4), and a number is not a price until it is written as one.
NOT_A_NUMBER = "Размер и порядок вводятся числами."
NOT_A_PAIR = "Панель прислала значение, которое не разбирается: обновите страницу."
LIKE_THE_PRODUCT = "как у товара"
# What an override is called when the attribute behind it is gone: the panel
# still shows the variant, and a name it cannot read is not a reason to hide it.
UNNAMED = "—"
ROUBLE = "₽"
# A non-breaking thin space between the thousands, so a price never wraps.
THOUSANDS = " "
OUTSIDE_THE_LIMITS = f"Значение не принято: размер — от 1 до {MAX_SIDE_MM} мм, количество — от 0 до {MAX_QUANTITY}."
NOT_YOURS = "У вас нет прав менять товары."

logger: Logger = structlog.get_logger(__name__)


class PanelInputError(ValueError):
    """Raised when the panel sends something its own script would never have composed."""


def builder_context(product_id: ProductId) -> dict[str, Any]:
    """Fill the panel of one saved product: its controls, its addresses and its rows."""
    return {
        "product_id": product_id,
        "max_side_mm": MAX_SIDE_MM,
        "max_quantity": MAX_QUANTITY,
        "controls": _controls(product_id),
        "rows": _rows(listed_variants(product_id)),
    }


def listed_variants(product_id: ProductId) -> VariantsList:
    """Ask the domain for the variants the panel draws."""
    return bridge().call(lambda scope: _all_variants(scope, product_id))


def forbidden() -> JsonResponse:
    """Answer the staff member who may not change products: every panel address writes or reads his aggregate."""
    return JsonResponse({"error": NOT_YOURS}, status=403)


def answered(request: HttpRequest, answer: Callable[[], dict[str, Any]]) -> JsonResponse:
    """Answer one panel request, turning a refusal into the JSON the script shows."""
    try:
        return JsonResponse(answer())
    except AppError as refusal:
        logger.warning("The variant builder was refused", code=type(refusal).code)
        return JsonResponse({"error": refusal_text(refusal)}, status=400)
    except ValidationError:
        logger.warning("The variant builder sent a value outside the input limits", path=request.path)
        return JsonResponse({"error": OUTSIDE_THE_LIMITS}, status=400)
    except PanelInputError as unreadable:
        logger.warning("The variant builder sent something unreadable", path=request.path)
        return JsonResponse({"error": str(unreadable)}, status=400)


def quoted(request: HttpRequest, product_id: ProductId) -> dict[str, Any]:
    """Price what stands in the panel right now, by the function that would save it."""
    form = QuoteVariantForm(**_assembled(request.GET))
    quote: QuotedVariant = bridge().call(lambda scope: _quoted(scope, product_id, form))
    return {"price_label": money_label(quote.price)}


def saved(request: HttpRequest, product_id: ProductId) -> dict[str, Any]:
    """Write what stands in the panel: a new variant, a rewritten one, or a copy at another size."""
    posted = request.POST
    target = _variant_id(posted)
    if target is not None and posted.get(DUPLICATE):
        assembled = _assembled(posted)
        duplicate = DuplicateVariantWithSizeForm(width_mm=assembled[WIDTH], height_mm=assembled[HEIGHT])
        bridge().call(lambda scope: _duplicated(scope, product_id, target, duplicate))
    elif target is not None:
        change = ChangeVariantForm(**_assembled(posted))
        bridge().call(lambda scope: _changed(scope, product_id, target, change))
    else:
        addition = AddVariantForm(**_assembled(posted))
        bridge().call(lambda scope: _added(scope, product_id, addition))
    return {"variants": _rows(listed_variants(product_id))}


def removed(request: HttpRequest, product_id: ProductId) -> dict[str, Any]:
    """Take one variant off the product and redraw what is left of the panel."""
    target = _variant_id(request.POST)
    if target is None:
        raise PanelInputError(NOT_A_PAIR)
    bridge().call(lambda scope: _removed(scope, product_id, target))
    return {"variants": _rows(listed_variants(product_id))}


def money_label(amount: Decimal) -> str:
    """Write a sum the way the site writes it: thousands apart, kopecks only when there are any."""
    roubles, _, kopecks = f"{amount:,.2f}".replace(",", THOUSANDS).partition(".")
    body = roubles if kopecks == "00" else f"{roubles},{kopecks}"
    return f"{body}{THOUSANDS}{ROUBLE}"


def size_label(variant: VariantModel) -> str:
    """Write the size of a variant the way the owner reads it."""
    return f"{variant.width_mm} × {variant.height_mm} мм"


def values_label(variant: VariantModel) -> str:
    """Say what a variant changes about the product, or that it changes nothing."""
    return ", ".join(_difference(override) for override in variant.overrides) or LIKE_THE_PRODUCT


def _difference(override: VariantOverrideModel) -> str:
    """Name one difference: a dictionary row by its name, a quantity by its number."""
    chosen = override.value_name if override.value_id is not None else override.quantity
    return f"{override.attribute_name or UNNAMED}: {chosen}"


def _rows(listed: VariantsList) -> list[dict[str, Any]]:
    """Spell the variants as the rows the script draws without knowing the domain."""
    return [
        {
            "variant_id": str(variant.id),
            "width_mm": variant.width_mm,
            "height_mm": variant.height_mm,
            "sort_order": variant.sort_order,
            "size_label": size_label(variant),
            "values_label": values_label(variant),
            "price_label": money_label(variant.price),
            "sets_product_price": variant.sets_product_price,
            "overrides": {
                str(override.attribute_id): str(override.value_id)
                if override.value_id is not None
                else str(override.quantity)
                for override in variant.overrides
            },
        }
        for variant in listed.items
    ]


def _controls(product_id: ProductId) -> list[dict[str, Any]]:
    """Build one control per attribute the product declares: an override replaces a declaration, never adds one."""
    # Imported here: the mirrors may not be touched before ``django.setup()``.
    from memiro.presentation.django_admin.models import (  # noqa: PLC0415
        Attribute,
        AttributeValue,
        ProductDeclaredValue,
    )

    declared = ProductDeclaredValue.objects.select_related("attribute").filter(product_id=product_id)
    controls: list[dict[str, Any]] = []
    for declaration in declared.order_by("attribute__sort_order", "attribute__name"):
        attribute: Attribute = declaration.attribute
        is_quantity = attribute.kind == AttributeKind.NUMBER.name
        rows = AttributeValue.objects.filter(attribute_id=attribute.id).order_by("sort_order", "name")
        controls.append(
            {
                "attribute_id": str(attribute.id),
                "name": attribute.name,
                "is_quantity": is_quantity,
                "values": [] if is_quantity else list(rows),
            },
        )
    return controls


def _assembled(sent: QueryDict) -> dict[str, Any]:
    """Read the panel's own fields into the words of the application form."""
    return {
        WIDTH: _whole(sent.get(WIDTH)),
        HEIGHT: _whole(sent.get(HEIGHT)),
        ORDER: _whole(sent.get(ORDER) or "0"),
        "overrides": _overrides(sent),
    }


def _overrides(sent: QueryDict) -> list[VariantOverrideForm]:
    """Read the controls the owner filled in: each names its attribute alongside its value."""
    chosen: list[VariantOverrideForm] = []
    for pair in _repeated(sent, VALUE):
        attribute_id, value = _pair(pair)
        chosen.append(VariantOverrideForm(attribute_id=attribute_id, value_id=UUID(hex=value)))
    for pair in _repeated(sent, QUANTITY):
        attribute_id, value = _pair(pair)
        chosen.append(VariantOverrideForm(attribute_id=attribute_id, quantity=_amount(value)))
    return chosen


def _repeated(sent: QueryDict, name: str) -> Sequence[str]:
    """Take every value the panel sent under one name: a control per declared value posts them all at once."""
    return [str(value) for value in sent.getlist(name)]


def _pair(sent: str) -> tuple[UUID, str]:
    """Split one control's answer into the attribute it belongs to and what stands in it."""
    attribute, _, value = sent.partition(":")
    try:
        return UUID(hex=attribute), value
    except ValueError as broken:
        raise PanelInputError(NOT_A_PAIR) from broken


def _variant_id(sent: Mapping[str, Any]) -> VariantId | None:
    """Read which variant the panel is acting on, if it names one at all."""
    named = sent.get(VARIANT)
    if not named:
        return None
    try:
        return UUID(hex=str(named))
    except ValueError as broken:
        raise PanelInputError(NOT_A_PAIR) from broken


def _whole(sent: object) -> int:
    """Read one whole number the owner typed, refusing what is not one."""
    try:
        return int(str(sent))
    except (TypeError, ValueError) as broken:
        raise PanelInputError(NOT_A_NUMBER) from broken


def _amount(sent: str) -> Decimal:
    """Read one consumption the owner typed, refusing what is not a number."""
    try:
        return Decimal(sent)
    except InvalidOperation as broken:
        raise PanelInputError(NOT_A_NUMBER) from broken


async def _all_variants(scope: AsyncContainer, product_id: ProductId) -> VariantsList:
    interactor = await scope.get(ListVariants)
    return await interactor.execute(product_id)


async def _quoted(scope: AsyncContainer, product_id: ProductId, form: QuoteVariantForm) -> QuotedVariant:
    interactor = await scope.get(QuoteVariant)
    return await interactor.execute(product_id, form)


async def _added(scope: AsyncContainer, product_id: ProductId, form: AddVariantForm) -> None:
    interactor = await scope.get(AddVariant)
    await interactor.execute(product_id, form)


async def _changed(
    scope: AsyncContainer,
    product_id: ProductId,
    variant_id: VariantId,
    form: ChangeVariantForm,
) -> None:
    interactor = await scope.get(ChangeVariant)
    await interactor.execute(product_id, variant_id, form)


async def _duplicated(
    scope: AsyncContainer,
    product_id: ProductId,
    variant_id: VariantId,
    form: DuplicateVariantWithSizeForm,
) -> None:
    interactor = await scope.get(DuplicateVariantWithSize)
    await interactor.execute(product_id, variant_id, form)


async def _removed(scope: AsyncContainer, product_id: ProductId, variant_id: VariantId) -> None:
    interactor = await scope.get(RemoveVariant)
    await interactor.execute(product_id, variant_id)
