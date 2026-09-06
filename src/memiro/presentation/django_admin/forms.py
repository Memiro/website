# django-stubs makes ModelForm and BaseInlineFormSet generic, but Django does
# not implement __class_getitem__ on them: the parameter cannot be written
# without a runtime TypeError (the mypy side of this is in pyproject.toml).
# Unparameterized, the instance a form carries and the rows a formset holds
# read as Unknown to basedpyright.
# pyright: reportMissingTypeArgument=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false
# pyright: reportUnknownParameterType=false
"""The fields of the attribute card, with the bounds of the input where the owner types them.

The bounds are imported from ``input_limits``, never spelled again here: the
application form and this one refuse the same value (§13.6).
"""

from typing import Any, override

from django import forms
from django.forms import BaseInlineFormSet

from memiro.application.common.input_limits import (
    MAX_AREA_M2,
    MAX_ATTRIBUTE_PARENTS,
    MAX_NAME_LENGTH,
    MAX_ORDER_TOTAL,
    MAX_RATE_AMOUNT,
    MAX_SIDE_MM,
    MAX_SURCHARGE_FACTOR,
    MIN_NAME_LENGTH,
)
from memiro.presentation.django_admin.models import Attribute, AttributeValue, PricingSettings, SizeSurcharge

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


class MaterialPriceRowForm(forms.ModelForm):
    """Строка «Материалов и цен»: всё, что владелец правит поперёк справочника."""

    rate_amount = forms.DecimalField(min_value=0, max_value=MAX_RATE_AMOUNT, label="Тариф")

    class Meta:
        model = AttributeValue
        fields = (
            "rate_unit",
            "rate_amount",
            "scaled_by_shape",
            "scaled_by_size_surcharge",
        )
        labels = {  # noqa: RUF012  # Django reads Meta options off the class as plain values
            "rate_unit": "Единица расхода",
            "scaled_by_shape": "Умножается формой",
            "scaled_by_size_surcharge": "Умножается наценкой за размер",
        }


class PricingSettingsForm(forms.ModelForm):
    """Границы расчёта: снизу — по чему считается малое зеркало, сверху — что берёт производство."""

    min_area = forms.DecimalField(min_value=0, max_value=MAX_AREA_M2, label="Минимальная площадь, м²")
    min_order_total = forms.DecimalField(min_value=0, max_value=MAX_ORDER_TOTAL, label="Минимальная сумма заказа, ₽")
    max_long_side_mm = forms.IntegerField(
        min_value=0,
        max_value=MAX_SIDE_MM,
        label="Наибольшая сторона, мм",
        help_text=(
            "Ноль значит «предела нет». Поднимайте предел только после того, "
            "как заведены ступени наценки: иначе сайт будет продавать крупные "
            "зеркала по цене метровых (ADR-0010)."
        ),
    )
    max_short_side_mm = forms.IntegerField(
        min_value=0,
        max_value=MAX_SIDE_MM,
        label="Вторая сторона, мм",
        help_text="Ноль значит «предела нет».",
    )

    class Meta:
        model = PricingSettings
        fields = (
            "min_area",
            "min_order_total",
            "max_long_side_mm",
            "max_short_side_mm",
        )


class SizeSurchargeTierForm(forms.ModelForm):
    """Ступень наценки: с какого размера изделие дорожает и во сколько раз."""

    from_long_side_mm = forms.IntegerField(min_value=0, max_value=MAX_SIDE_MM, label="Наибольшая сторона от, мм")
    factor = forms.DecimalField(min_value=0, max_value=MAX_SURCHARGE_FACTOR, label="Коэффициент")

    class Meta:
        model = SizeSurcharge
        fields = (
            "from_long_side_mm",
            "factor",
        )


# One blank row under the stored ones, so the owner always has somewhere to
# type the next tier.
BLANK_TIER_ROWS = 1

# The name the mirror gives the composite key of a tier, and the name Django's
# inline template looks the row's key up by.
TIER_KEY_FIELD = "pk"


class SizeSurchargeFormSet(BaseInlineFormSet):
    """Ступени наценки: набор заменяется целиком, поэтому строки заводятся заново."""

    @override
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Show every stored tier as a fresh row: the composite key of a tier is not a form field."""
        super().__init__(*args, **kwargs)
        stored = list(self.get_queryset())
        self.initial_extra = [{"from_long_side_mm": tier.from_long_side_mm, "factor": tier.factor} for tier in stored]
        self.extra = len(stored) + BLANK_TIER_ROWS

    @override
    def initial_form_count(self) -> int:
        """Keep every row new: no tier is "the same tier" as one the set held before."""
        return 0

    @override
    def add_fields(self, form: forms.ModelForm, index: int | None) -> None:
        """Blank the key of the row: the composite key of a tier is a pair of columns, not a form value.

        Django renders the key of an inline row into a hidden field and reads
        it back as JSON; the pair it renders for a composite key is not JSON,
        and a row of a replaced set has no identity to carry anyway.
        """
        super().add_fields(form, index)
        form.fields[TIER_KEY_FIELD] = forms.Field(required=False, disabled=True, widget=forms.HiddenInput)
