from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class CategoryQuerySet(models.QuerySet):
    def visible(self) -> CategoryQuerySet:
        """Категории, у которых есть опубликованные товары."""
        return self.filter(products__is_published=True).distinct()


class Category(models.Model):
    """Плоский раздел каталога; иерархии нет (CONTEXT.md)."""

    name = models.CharField("название", max_length=100)
    slug = models.SlugField("слаг", unique=True)
    order = models.PositiveIntegerField("порядок", default=0)

    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ("order", "name")

    def __str__(self) -> str:
        return self.name


class Attribute(models.Model):
    """Фильтруемая характеристика, привязанная к категории (ADR-0002)."""

    class Kind(models.TextChoices):
        CHOICE = "choice", "выбор из списка"
        BOOLEAN = "boolean", "да/нет"
        NUMBER = "number", "число"

    category = models.ForeignKey(
        Category,
        verbose_name="категория",
        on_delete=models.CASCADE,
        related_name="attributes",
    )
    name = models.CharField("название", max_length=100)
    slug = models.SlugField("слаг")
    kind = models.CharField(
        "тип значения",
        max_length=10,
        choices=Kind.choices,
        default=Kind.CHOICE,
    )
    order = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "атрибут"
        verbose_name_plural = "атрибуты"
        ordering = ("order", "name")
        constraints = (
            models.UniqueConstraint(
                fields=("category", "slug"),
                name="attribute_slug_unique_per_category",
            ),
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"

    def belongs_to(self, category_id: int | None) -> bool:
        return self.category_id == category_id

    def clean(self) -> None:
        """Категорию и тип атрибута, уже назначенного товарам, не сменить.

        Иначе товары молча остаются со значениями чужой категории или
        не соответствующими типу.
        """
        if self._state.adding:
            return
        stored = (
            Attribute.objects.filter(pk=self.pk)
            .values("category_id", "kind")
            .first()
        )
        if stored is None or not self.product_values.exists():
            return
        errors: dict[str, str] = {}
        if stored["category_id"] != self.category_id:
            errors["category"] = (
                "Нельзя сменить категорию: атрибут уже назначен товарам."
            )
        if stored["kind"] != self.kind:
            errors["kind"] = (
                "Нельзя сменить тип: атрибут уже назначен товарам."
            )
        if errors:
            raise ValidationError(errors)


class AttributeValue(models.Model):
    """Значение из справочника атрибута типа «выбор из списка»."""

    attribute = models.ForeignKey(
        Attribute,
        verbose_name="атрибут",
        on_delete=models.CASCADE,
        related_name="values",
    )
    value = models.CharField("значение", max_length=100)
    order = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "значение атрибута"
        verbose_name_plural = "значения атрибута"
        ordering = ("order", "value")
        constraints = (
            models.UniqueConstraint(
                fields=("attribute", "value"),
                name="attribute_value_unique_per_attribute",
            ),
        )

    def __str__(self) -> str:
        return self.value


class Product(models.Model):
    """Изделие под заказ; наличия нет, цена обязательна (CONTEXT.md)."""

    category = models.ForeignKey(
        Category,
        verbose_name="категория",
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField("название", max_length=200)
    slug = models.SlugField("слаг", unique=True)
    price = models.PositiveIntegerField(
        "цена «от», ₽",
        validators=[MinValueValidator(1)],
    )
    description = models.TextField("описание", blank=True)
    # Артикулы старого каталога неуникальны — уникальность не навязываем
    article = models.CharField("артикул", max_length=50, blank=True)
    photo_small = models.ImageField(
        "фото малое",
        upload_to="products/small/",
        blank=True,
    )
    photo_large = models.ImageField(
        "фото большое",
        upload_to="products/large/",
        blank=True,
    )
    is_published = models.BooleanField("опубликован", default=False)
    is_popular = models.BooleanField("популярное", default=False)
    is_promo = models.BooleanField("акция", default=False)
    order = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"
        ordering = ("order", "name")

    def __str__(self) -> str:
        return self.name


class ProductImage(models.Model):
    """Кадр галереи товара."""

    product = models.ForeignKey(
        Product,
        verbose_name="товар",
        on_delete=models.CASCADE,
        related_name="gallery",
    )
    image = models.ImageField("изображение", upload_to="products/gallery/")
    order = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "фото галереи"
        verbose_name_plural = "галерея"
        ordering = ("order", "pk")

    def __str__(self) -> str:
        return f"Фото {self.pk} — {self.product}"


# Какое поле ProductAttribute хранит значение атрибута каждого типа;
# единственное место, где тип разворачивается в поле
VALUE_FIELD_BY_KIND = {
    Attribute.Kind.CHOICE: "value_option",
    Attribute.Kind.BOOLEAN: "value_bool",
    Attribute.Kind.NUMBER: "value_number",
}


class ProductAttribute(models.Model):
    """Значение атрибута у товара: заполняется поле под тип атрибута."""

    product = models.ForeignKey(
        Product,
        verbose_name="товар",
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )
    attribute = models.ForeignKey(
        Attribute,
        verbose_name="атрибут",
        # PROTECT: атрибут, назначенный товарам, не удаляется молча —
        # сначала снять его с товаров
        on_delete=models.PROTECT,
        related_name="product_values",
    )
    value_option = models.ForeignKey(
        AttributeValue,
        verbose_name="значение из списка",
        # PROTECT: чистка справочника не должна молча стирать
        # характеристики товаров
        on_delete=models.PROTECT,
        related_name="product_assignments",
        null=True,
        blank=True,
    )
    value_bool = models.BooleanField("да/нет", null=True, blank=True)
    value_number = models.DecimalField(
        "число",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "значение атрибута товара"
        verbose_name_plural = "атрибуты товара"
        constraints = (
            models.UniqueConstraint(
                fields=("product", "attribute"),
                name="one_value_per_product_attribute",
            ),
        )

    def __str__(self) -> str:
        return f"{self.attribute}: {self.display_value}"

    @property
    def display_value(self) -> str:
        if self.value_option_id:
            return str(self.value_option)
        if self.value_bool is not None:
            return "да" if self.value_bool else "нет"
        if self.value_number is not None:
            return str(self.value_number)
        return "—"

    def clean(self) -> None:
        if not self.attribute_id:
            return
        errors: dict[str, str] = {}
        if self.product_id and not self.attribute.belongs_to(
            self.product.category_id
        ):
            errors["attribute"] = "Атрибут принадлежит другой категории."
        errors.update(self._kind_errors())
        if errors:
            raise ValidationError(errors)

    def _kind_errors(self) -> dict[str, str]:
        expected_field = VALUE_FIELD_BY_KIND[
            Attribute.Kind(self.attribute.kind)
        ]
        filled = {
            "value_option": self.value_option_id is not None,
            "value_bool": self.value_bool is not None,
            "value_number": self.value_number is not None,
        }
        errors = {
            field: "Не соответствует типу атрибута."
            for field, is_set in filled.items()
            if is_set and field != expected_field
        }
        if not filled[expected_field]:
            errors[expected_field] = "Заполните значение под тип атрибута."
        option = self.value_option
        if (
            expected_field == "value_option"
            and option is not None
            and option.attribute_id != self.attribute_id
        ):
            errors["value_option"] = "Значение справочника другого атрибута."
        return errors
