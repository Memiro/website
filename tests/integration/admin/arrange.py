"""What the write tests of the admin card arrange and post."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from html import unescape
from typing import Any

from dishka import AsyncContainer

from memiro.application.common.input_limits import MAX_ATTRIBUTE_VALUES, MAX_SIZE_SURCHARGES
from memiro.application.manage_attributes import AttributeValueForm, CreateAttribute, CreateAttributeForm
from memiro.application.manage_pricing_settings import (
    ChangePricingSettings,
    ChangePricingSettingsForm,
    SizeSurchargeRowForm,
)
from memiro.application.manage_products import (
    AddImage,
    AddImageForm,
    AddVariant,
    AddVariantForm,
    CreatedProductImage,
    CreateProduct,
    CreateProductForm,
    ListVariants,
    RemoveVariant,
)
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.common.identifiers import AttributeId, AttributeValueId, CategoryId, ProductId, VariantId
from memiro.presentation.django_admin.bridge import bridge
from tests.common.factory.catalog import CATEGORY, PRODUCT

INLINE_PREFIX = "values"


@dataclass(frozen=True, slots=True)
class PricingBounds:
    """The four bounds of calculation, as the owner types them on the screen."""

    min_area: str
    min_order_total: str
    max_long_side_mm: int
    max_short_side_mm: int


def value_form(*, name: str, amount: str = "2500", sort_order: int = 1) -> AttributeValueForm:
    """Build one dictionary row for an attribute a test arranges."""
    return AttributeValueForm(
        name=name,
        rate_amount=Decimal(amount),
        rate_unit=Unit.LINEAR_METER,
        scaled_by_shape=False,
        scaled_by_size_surcharge=False,
        marks_absence=False,
        sort_order=sort_order,
    )


def card_fields(*, name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Spell one card the way the admin form hands it to the interactors, once it is valid."""
    # Imported here: the mirror models may not be touched before the session
    # fixture has run ``django.setup()``. The section is built, not read back —
    # only its identifier travels, so no query is made.
    from memiro.presentation.django_admin.models import Category  # noqa: PLC0415

    root: dict[str, Any] = {
        "category": Category(id=CATEGORY),
        "name": name,
        "kind": AttributeKind.SELECT.name,
        "parents": [],
        "is_customer_changeable": True,
        "is_filterable": False,
        "sort_order": 0,
    }
    rows: list[dict[str, Any]] = [
        {
            "name": "Строка",
            "rate_amount": Decimal(2500),
            "rate_unit": Unit.LINEAR_METER.name,
            "scaled_by_shape": False,
            "scaled_by_size_surcharge": False,
            "marks_absence": False,
            "sort_order": 1,
        },
    ]
    return root, rows


def arranged_attribute(*, name: str, values: Sequence[AttributeValueForm]) -> AttributeId:
    """Put one attribute of the demo category into the database through its own command."""
    form = CreateAttributeForm(
        category_id=CATEGORY,
        name=name,
        kind=AttributeKind.SELECT,
        values=list(values),
    )
    return bridge().call(lambda scope: _created(scope, form))


async def _created(scope: AsyncContainer, form: CreateAttributeForm) -> AttributeId:
    """Run the creating interactor in a REQUEST scope of the admin's own container."""
    interactor = await scope.get(CreateAttribute)
    created = await interactor.execute(form)
    return created.id


def row(  # noqa: PLR0913  # one keyword per column of the dictionary row the card posts
    *,
    name: str,
    amount: str = "2500",
    unit: Unit = Unit.LINEAR_METER,
    sort_order: int = 1,
    value_id: AttributeId | None = None,
    marks_absence: bool = False,
) -> dict[str, str]:
    """Spell one inline row the way the card posts it."""
    posted = {
        "name": name,
        "rate_amount": amount,
        "rate_unit": unit.name,
        "sort_order": str(sort_order),
    }
    posted |= {"id": str(value_id)} if value_id is not None else {}
    posted |= {"marks_absence": "on"} if marks_absence else {}
    return posted


def card_post(  # noqa: PLR0913  # one keyword per field of the card the owner fills in
    *,
    name: str,
    rows: Sequence[Mapping[str, str]],
    kind: AttributeKind = AttributeKind.SELECT,
    sort_order: int = 0,
    parents: Sequence[AttributeId] = (),
    kept_rows: int = 0,
) -> dict[str, Any]:
    """Spell the whole card — root and inline management form — as one POST body."""
    posted: dict[str, Any] = {
        "category": str(CATEGORY),
        "name": name,
        "kind": kind.name,
        "sort_order": str(sort_order),
        "is_customer_changeable": "on",
        "parents": [str(parent) for parent in parents],
        f"{INLINE_PREFIX}-TOTAL_FORMS": str(len(rows)),
        f"{INLINE_PREFIX}-INITIAL_FORMS": str(kept_rows),
        f"{INLINE_PREFIX}-MIN_NUM_FORMS": "0",
        f"{INLINE_PREFIX}-MAX_NUM_FORMS": str(MAX_ATTRIBUTE_VALUES),
    }
    for number, posted_row in enumerate(rows):
        posted |= {f"{INLINE_PREFIX}-{number}-{field}": value for field, value in posted_row.items()}
    return posted


TIER_PREFIX = "size_surcharges"
FLAT_PREFIX = "form"


def priced_row(  # noqa: PLR0913  # one keyword per column of the flat list the owner may move
    *,
    value_id: AttributeValueId,
    amount: str = "3000",
    unit: Unit = Unit.LINEAR_METER,
    scaled_by_shape: bool = False,
    scaled_by_size_surcharge: bool = False,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Spell one row of «Материалы и цены» the way the changelist posts it."""
    posted = {
        "id": str(value_id),
        "rate_unit": unit.name,
        "rate_amount": amount,
    }
    posted |= {"scaled_by_shape": "on"} if scaled_by_shape else {}
    posted |= {"scaled_by_size_surcharge": "on"} if scaled_by_size_surcharge else {}
    posted |= dict(extra or {})
    return posted


def priced_list_post(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    """Spell the edited rows of the flat list as the changelist's own POST body."""
    posted: dict[str, Any] = {
        f"{FLAT_PREFIX}-TOTAL_FORMS": str(len(rows)),
        f"{FLAT_PREFIX}-INITIAL_FORMS": str(len(rows)),
        f"{FLAT_PREFIX}-MIN_NUM_FORMS": "0",
        f"{FLAT_PREFIX}-MAX_NUM_FORMS": str(len(rows)),
        "_save": "",
    }
    for number, posted_row in enumerate(rows):
        posted |= {f"{FLAT_PREFIX}-{number}-{field}": value for field, value in posted_row.items()}
    return posted


def tier(*, from_long_side_mm: int, factor: str) -> dict[str, str]:
    """Spell one surcharge tier the way the inline posts it."""
    return {"from_long_side_mm": str(from_long_side_mm), "factor": factor}


def pricing_post(
    *,
    bounds: PricingBounds,
    tiers: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """Spell the whole screen of calculation parameters — bounds and tiers — as one POST body."""
    posted: dict[str, Any] = {
        "min_area": bounds.min_area,
        "min_order_total": bounds.min_order_total,
        "max_long_side_mm": str(bounds.max_long_side_mm),
        "max_short_side_mm": str(bounds.max_short_side_mm),
        f"{TIER_PREFIX}-TOTAL_FORMS": str(len(tiers)),
        f"{TIER_PREFIX}-INITIAL_FORMS": "0",
        f"{TIER_PREFIX}-MIN_NUM_FORMS": "0",
        f"{TIER_PREFIX}-MAX_NUM_FORMS": str(MAX_SIZE_SURCHARGES),
    }
    for number, posted_tier in enumerate(tiers):
        posted |= {f"{TIER_PREFIX}-{number}-{field}": value for field, value in posted_tier.items()}
    return posted


def arranged_pricing_settings(bounds: PricingBounds, tiers: Sequence[tuple[int, str]] = ()) -> None:
    """Put known calculation parameters into the database through their own command."""
    form = ChangePricingSettingsForm(
        min_area=Decimal(bounds.min_area),
        min_order_total=Decimal(bounds.min_order_total),
        max_long_side_mm=bounds.max_long_side_mm,
        max_short_side_mm=bounds.max_short_side_mm,
        surcharges=[
            SizeSurchargeRowForm(from_long_side_mm=threshold, factor=Decimal(factor)) for threshold, factor in tiers
        ],
    )
    bridge().call(lambda scope: _changed(scope, form))


async def _changed(scope: AsyncContainer, form: ChangePricingSettingsForm) -> None:
    """Run the parameters interactor in a REQUEST scope of the admin's own container."""
    interactor = await scope.get(ChangePricingSettings)
    await interactor.execute(form)


# What the browser sends back: every input the card rendered, the empty extra
# row and the template row of the inline aside.
_INPUT = re.compile(r"<input[^>]*>")
_NAME = re.compile(r'name="([^"]+)"')
_VALUE = re.compile(r'value="([^"]*)"')
TEMPLATE_ROW = f"{TIER_PREFIX}-__prefix__"


def rendered_form(shown: str) -> dict[str, str]:
    """Read back the card the owner is looking at, as the fields his browser would post."""
    posted: dict[str, str] = {}
    for tag in _INPUT.findall(shown):
        name = _NAME.search(tag)
        value = _VALUE.search(tag)
        if name is None or name.group(1).startswith(TEMPLATE_ROW) or 'type="checkbox"' in tag:
            continue
        posted[name.group(1)] = unescape(value.group(1)) if value else ""
    return posted


def arranged_variant(*, width_mm: int, height_mm: int) -> VariantId:
    """Put one precalculated variant on the demo product through its own command."""
    form = AddVariantForm(width_mm=width_mm, height_mm=height_mm, overrides=[], sort_order=0)
    return bridge().call(lambda scope: _added(scope, form))


def removed_variant(variant_id: VariantId) -> None:
    """Take the arranged variant off the demo product again: the admin's database outlives one test."""
    bridge().call(lambda scope: _removed(scope, variant_id))


async def _added(scope: AsyncContainer, form: AddVariantForm) -> VariantId:
    """Run the adding interactor in a REQUEST scope of the admin's own container."""
    interactor = await scope.get(AddVariant)
    created = await interactor.execute(PRODUCT, form)
    return created.id


async def _removed(scope: AsyncContainer, variant_id: VariantId) -> None:
    """Run the removing interactor in a REQUEST scope of the admin's own container."""
    interactor = await scope.get(RemoveVariant)
    await interactor.execute(PRODUCT, variant_id)


def cleared_variants() -> None:
    """Take every variant off the demo product again: the admin's database outlives one test."""
    bridge().call(_cleared)


async def _cleared(scope: AsyncContainer) -> None:
    """Run the listing and the removals in one REQUEST scope of the admin's own container."""
    listing = await scope.get(ListVariants)
    removing = await scope.get(RemoveVariant)
    for variant in (await listing.execute(PRODUCT)).items:
        await removing.execute(PRODUCT, variant.id)


# Photos are an inline of the product card: Django reads their management form
# on every save, whether or not the owner touched a row.
PHOTO_PREFIX = "images"


def product_post(  # noqa: PLR0913  # one keyword per field of the card the owner fills in
    *,
    name: str,
    slug: str = "",
    description: str = "",
    category: CategoryId = CATEGORY,
    declared: Sequence[tuple[AttributeId, str]] = (),
    photos: int = 0,
    is_published: bool = True,
) -> dict[str, Any]:
    """Spell the whole product card — the root and the declared values — as one POST body."""
    # Imported here: the card fields are named after the attributes of the
    # section, and the mirror may not be touched before ``django.setup()``.
    from memiro.presentation.django_admin.forms import declared_field_name  # noqa: PLC0415

    posted: dict[str, Any] = {
        "category": str(category),
        "name": name,
        "slug": slug,
        "description": description,
        f"{PHOTO_PREFIX}-TOTAL_FORMS": str(photos),
        f"{PHOTO_PREFIX}-INITIAL_FORMS": str(photos),
        f"{PHOTO_PREFIX}-MIN_NUM_FORMS": "0",
        f"{PHOTO_PREFIX}-MAX_NUM_FORMS": str(photos),
    }
    posted |= {"is_published": "on"} if is_published else {}
    posted |= {declared_field_name(attribute_id): value for attribute_id, value in declared}
    return posted


def category_post(*, name: str, slug: str, sort_order: int = 0) -> dict[str, str]:
    """Spell the card of a section: content without rules, written straight to the mirror."""
    return {"name": name, "slug": slug, "sort_order": str(sort_order)}


def arranged_product(*, name: str, slug: str = "") -> ProductId:
    """Put one product of the demo section into the database through its own command."""
    form = CreateProductForm(category_id=CATEGORY, name=name, slug=slug)
    return bridge().call(lambda scope: _entered(scope, form))


def arranged_photo(product_id: ProductId, *, content: bytes) -> str:
    """Put one photo on a product through its own command, and answer with the key the storage issued."""
    form = AddImageForm(filename="mirror.jpg", content=content)
    added: CreatedProductImage = bridge().call(lambda scope: _uploaded(scope, product_id, form))
    return added.key


async def _uploaded(scope: AsyncContainer, product_id: ProductId, form: AddImageForm) -> CreatedProductImage:
    """Run the uploading interactor in a REQUEST scope of the admin's own container."""
    interactor = await scope.get(AddImage)
    return await interactor.execute(product_id, form)


async def _entered(scope: AsyncContainer, form: CreateProductForm) -> ProductId:
    """Run the creating interactor in a REQUEST scope of the admin's own container."""
    interactor = await scope.get(CreateProduct)
    created = await interactor.execute(form)
    return created.id
