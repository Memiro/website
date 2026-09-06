# django-stubs makes ModelForm generic, but Django does not implement
# __class_getitem__ on it: the parameter cannot be written without a runtime
# TypeError (the mypy side of this is in pyproject.toml). Unparameterized, the
# instance the form carries reads as Unknown to basedpyright.
# pyright: reportMissingTypeArgument=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
"""The fields of the attribute card, with the bounds of the input where the owner types them.

The bounds are imported from ``input_limits``, never spelled again here: the
application form and this one refuse the same value (§13.6).
"""

from typing import Any, override

from django import forms

from memiro.application.common.input_limits import (
    MAX_ATTRIBUTE_PARENTS,
    MAX_NAME_LENGTH,
    MAX_RATE_AMOUNT,
    MIN_NAME_LENGTH,
)
from memiro.presentation.django_admin.models import Attribute, AttributeValue

PARENTS_FIELD = "parents"


class AttributeCardForm(forms.ModelForm):
    """Корень атрибута: название, вид, зависимости и место в списке."""

    name = forms.CharField(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH, label="Название")
    sort_order = forms.IntegerField(min_value=0, initial=0, label="Порядок")
    parents = forms.ModelMultipleChoiceField(
        queryset=Attribute.objects.all(),
        required=False,
        label="Зависит от",
        help_text="Атрибут показывается покупателю, только когда выбран один из этих атрибутов.",
    )

    class Meta:
        model = Attribute
        fields = (
            "category",
            "name",
            "kind",
            "is_customer_changeable",
            "is_filterable",
            "sort_order",
        )
        labels = {  # noqa: RUF012  # Django reads Meta options off the class as plain values
            "category": "Раздел",
            "kind": "Вид",
            "is_customer_changeable": "Меняет покупатель",
            "is_filterable": "Строит фильтр",
        }

    @override
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Show the dependencies the attribute was stored with: the column is an array of identifiers."""
        super().__init__(*args, **kwargs)
        self.fields[PARENTS_FIELD].initial = list(self.instance.parent_ids or [])

    def clean_parents(self) -> list[Attribute]:
        """Refuse more dependencies than the application form accepts."""
        parents = list(self.cleaned_data[PARENTS_FIELD])
        if len(parents) > MAX_ATTRIBUTE_PARENTS:
            message = f"Не больше {MAX_ATTRIBUTE_PARENTS} зависимостей."
            raise forms.ValidationError(message)
        return parents


class AttributeValueRowForm(forms.ModelForm):
    """Строка справочника: название, тариф и признаки расчёта."""

    name = forms.CharField(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH, label="Название")
    rate_amount = forms.DecimalField(min_value=0, max_value=MAX_RATE_AMOUNT, label="Тариф")
    sort_order = forms.IntegerField(min_value=0, initial=0, label="Порядок")

    class Meta:
        model = AttributeValue
        fields = (
            "name",
            "rate_amount",
            "rate_unit",
            "scaled_by_shape",
            "scaled_by_size_surcharge",
            "marks_absence",
            "sort_order",
        )
        labels = {  # noqa: RUF012  # Django reads Meta options off the class as plain values
            "rate_unit": "Единица расхода",
            "scaled_by_shape": "Умножается формой",
            "scaled_by_size_surcharge": "Умножается наценкой за размер",
            "marks_absence": "Означает отсутствие",
        }
