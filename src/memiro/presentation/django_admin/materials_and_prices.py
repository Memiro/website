# django-stubs types every model field as a generic descriptor, and only its
# mypy plugin solves the parameters; basedpyright sees `Unknown` on each column
# a mirror row is read through here.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""What the flat price list sends: one edited row as the whole dictionary of its attribute.

The screen shows the values of every attribute side by side, and the owner
edits the price half of a row there. The command is still the one the card of
the attribute sends — a second truth about the price is what decision 4
forbids — so the row travels back inside the dictionary it belongs to, its
neighbours unchanged.
"""

from dishka import AsyncContainer

from memiro.application.manage_attributes import ReplacementValueForm, ReplaceValues, ReplaceValuesForm
from memiro.entities.catalog.attribute.rate import Unit
from memiro.entities.common.identifiers import AttributeId
from memiro.presentation.django_admin.models import AttributeValue
from memiro.presentation.django_admin.writes import sent

# The columns of the flat list the owner may move; the rest of the row travels
# back exactly as it was stored.
PRICED_COLUMNS = (
    "rate_unit",
    "rate_amount",
    "scaled_by_shape",
    "scaled_by_size_surcharge",
)


def restate_priced_row(edited: AttributeValue) -> None:
    """Send the dictionary of one attribute with the row the owner priced put back into it."""
    dictionary = AttributeValue.objects.filter(attribute_id=edited.attribute_id).order_by("sort_order", "name")
    values = [_as_replacement(edited if row.id == edited.id else row) for row in dictionary]
    sent(lambda scope: _replace(scope, edited.attribute_id, ReplaceValuesForm(values=values)))


def _as_replacement(row: AttributeValue) -> ReplacementValueForm:
    """Read one stored dictionary row in the words of the application form."""
    return ReplacementValueForm(
        id=row.id,
        name=row.name,
        rate_amount=row.rate_amount,
        # The mirror stores the member name of the domain enum; the
        # application form speaks the enum itself.
        rate_unit=Unit[row.rate_unit],
        scaled_by_shape=row.scaled_by_shape,
        scaled_by_size_surcharge=row.scaled_by_size_surcharge,
        marks_absence=row.marks_absence,
        sort_order=row.sort_order,
    )


async def _replace(scope: AsyncContainer, attribute_id: AttributeId, form: ReplaceValuesForm) -> None:
    interactor = await scope.get(ReplaceValues)
    await interactor.execute(attribute_id, form)
