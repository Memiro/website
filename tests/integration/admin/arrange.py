"""What the write tests of the admin card arrange and post."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from dishka import AsyncContainer

from memiro.application.common.input_limits import MAX_ATTRIBUTE_VALUES
from memiro.application.manage_attributes import AttributeValueForm, CreateAttribute, CreateAttributeForm
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.common.identifiers import AttributeId
from memiro.presentation.django_admin.bridge import bridge
from tests.common.factory.catalog import CATEGORY

INLINE_PREFIX = "values"


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
