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

from typing import Any, cast, override
from uuid import UUID

from django import forms
from django.core.validators import RegexValidator
from django.forms import BaseInlineFormSet

from memiro.application.common.input_limits import (
    MAX_AREA_M2,
    MAX_ATTRIBUTE_PARENTS,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_ORDER_TOTAL,
    MAX_QUANTITY,
    MAX_RATE_AMOUNT,
    MAX_SIDE_MM,
    MAX_SURCHARGE_FACTOR,
    MIN_NAME_LENGTH,
)
from memiro.application.manage_products import SLUG_PATTERN
from memiro.entities.catalog.attribute.entity import AttributeKind
from memiro.entities.common.slug import MAX_SLUG_LENGTH
from memiro.presentation.django_admin.models import (
    Attribute,
    AttributeValue,
    Category,
    PricingSettings,
    Product,
    ProductDeclaredValue,
    SizeSurcharge,
)

PARENTS_FIELD = "parents"

# One blank row under the stored ones, so the owner always has somewhere to
# type the next tier.
BLANK_TIER_ROWS = 1

# The name the mirror gives the composite key of a tier, and the name Django's
# inline template looks the row's key up by.
TIER_KEY_FIELD = "pk"

# The prefix a card field carries when it declares an attribute of the section
# rather than a column of the product itself.
DECLARED_PREFIX = "declared_"

SLUG_MESSAGE = "Адрес — латинские слова через дефис."
# The declared fields on a card are built from the section the product is in
# today, so a save that also moves it would send the old section's values to
# the new one: the domain refuses them, and the root has already committed.
MOVE_CARRIES_VALUES = (
    "Раздел меняется отдельным сохранением: сначала перенесите товар, а значения нового раздела объявите следующим."
)


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


class ProductCardForm(forms.ModelForm):
    """Карточка товара: корень, а под ним по полю на каждый атрибут раздела."""

    name = forms.CharField(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH, label="Название")
    slug = forms.CharField(
        required=False,
        max_length=MAX_SLUG_LENGTH,
        validators=[RegexValidator(SLUG_PATTERN, message=SLUG_MESSAGE)],
        label="Адрес",
        help_text="Пустой адрес выводится из названия; дальше он правится руками.",
    )
    description = forms.CharField(
        required=False,
        max_length=MAX_DESCRIPTION_LENGTH,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Описание",
    )

    class Meta:
        model = Product
        fields = (
            "category",
            "name",
            "slug",
            "description",
            "is_published",
            "hides_calculated_price",
        )
        labels = {  # noqa: RUF012  # Django reads Meta options off the class as plain values
            "category": "Раздел",
            "is_published": "Опубликован",
            "hides_calculated_price": "Не называть цену расчёта",
        }

    @override
    def validate_unique(self) -> None:
        """Leave the address to the transaction that writes it: a card cannot see a race (``product.md``, п. 13)."""

    @override
    def clean(self) -> dict[str, Any]:
        """Refuse a move that carries declared values with it: they are the values of the section being left."""
        cleaned = cast("dict[str, Any]", super().clean())
        section = cleaned.get("category")
        if self.instance.pk is None or section is None or section.pk == self.initial.get("category"):
            return cleaned
        declared = (field for field in self.fields if field.startswith(DECLARED_PREFIX))
        if any(cleaned.get(field) is not None for field in declared):
            raise forms.ValidationError(MOVE_CARRIES_VALUES)
        return cleaned

    @override
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Show what the product declares today: the fields themselves are built by the screen."""
        super().__init__(*args, **kwargs)
        for value in ProductDeclaredValue.objects.filter(product_id=self.instance.pk):
            declared: UUID = value.attribute_id  # pyright: ignore[reportAttributeAccessIssue]  # the raw column behind a mirror foreign key
            chosen: UUID | None = value.value_id  # pyright: ignore[reportAttributeAccessIssue]  # the raw column behind a mirror foreign key
            field = declared_field_name(declared)
            if field in self.fields:
                self.initial[field] = value.quantity if chosen is None else chosen


def declared_field_name(attribute_id: UUID) -> str:
    """Name the card field one attribute of the section is declared in."""
    return f"{DECLARED_PREFIX}{attribute_id.hex}"


def declared_attribute_id(field: str) -> UUID:
    """Read back which attribute a card field declares."""
    return UUID(hex=field.removeprefix(DECLARED_PREFIX))


def declared_value_fields(category_id: UUID) -> dict[str, forms.Field]:
    """Build one field per attribute of the section, its kind deciding what the owner types."""
    attributes = Attribute.objects.filter(category_id=category_id).order_by("sort_order", "name")
    return {declared_field_name(attribute.id): _declared_field(attribute) for attribute in attributes}


def _declared_field(attribute: Attribute) -> forms.Field:
    """Build the field of one attribute: a number is typed, everything else is chosen."""
    label = attribute.name
    if attribute.kind == AttributeKind.NUMBER.name:
        return forms.DecimalField(min_value=0, max_value=MAX_QUANTITY, required=False, label=label)
    return forms.ModelChoiceField(
        queryset=AttributeValue.objects.filter(attribute_id=attribute.id).order_by("sort_order", "name"),
        required=False,
        label=label,
    )


class CategoryCardForm(forms.ModelForm):
    """Карточка раздела: название, адрес и место в списке — правил у раздела нет, границы ввода есть (§13.6)."""

    name = forms.CharField(min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH, label="Название")
    # The address of a section is typed, not derived: there is no interactor
    # behind this card to transliterate a name into one.
    slug = forms.CharField(
        max_length=MAX_SLUG_LENGTH,
        validators=[RegexValidator(SLUG_PATTERN, message=SLUG_MESSAGE)],
        label="Адрес",
    )

    class Meta:
        model = Category
        fields = (
            "name",
            "slug",
            "sort_order",
        )
        labels = {"sort_order": "Порядок"}  # noqa: RUF012  # Django reads Meta options off the class as plain values
