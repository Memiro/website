from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import Resolver404, resolve, reverse

if TYPE_CHECKING:
    from decimal import Decimal

    from django.db.models.fields.files import ImageFieldFile


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


# Витринный порядок «сначала популярные»: один кортеж на весь проект
POPULAR_ORDERING = ("-is_popular", "order", "name")


class ProductQuerySet(models.QuerySet):
    def published(self) -> ProductQuerySet:
        return self.filter(is_published=True)

    def by_popularity(self) -> ProductQuerySet:
        return self.order_by(*POPULAR_ORDERING)


class Product(models.Model):
    """Изделие под заказ; наличия нет, цена обязательна (CONTEXT.md)."""

    category = models.ForeignKey(
        Category,
        verbose_name="категория",
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField("название", max_length=200)
    # 120, а не 50 по умолчанию: у названий вроде «Зеркало с контурной
    # подсветкой в чёрной алюминиевой раме с вырезом Matrix» слаг
    # длиннее, и на PostgreSQL такая вставка падает
    slug = models.SlugField("слаг", unique=True, max_length=120)
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
    # Для сортировки каталога «новинки»
    created_at = models.DateTimeField("создан", auto_now_add=True)
    is_popular = models.BooleanField("популярное", default=False)
    is_promo = models.BooleanField("акция", default=False)
    order = models.PositiveIntegerField("порядок", default=0)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"
        ordering = ("order", "name")

    def __str__(self) -> str:
        return self.name

    @property
    def main_photo(self) -> ImageFieldFile | None:
        """Главный кадр товара: большое фото, иначе малое.

        Пустой ImageField ложный, но не None — наружу отдаём None,
        чтобы шаблон и разметка проверяли одно и то же.
        """
        return self.photo_large or self.photo_small or None


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


# Токены значений атрибута «да/нет» в querystring фильтра каталога
BOOL_TOKENS = {"1": True, "0": False}

# Те же значения словами — в характеристиках товара и условиях посадочной
BOOL_LABELS = {True: "да", False: "нет"}

# Какое поле ProductAttribute хранит значение атрибута каждого типа;
# единственное место, где тип разворачивается в поле
VALUE_FIELD_BY_KIND = {
    Attribute.Kind.CHOICE: "value_option",
    Attribute.Kind.BOOLEAN: "value_bool",
    Attribute.Kind.NUMBER: "value_number",
}


def value_kind_errors(
    attribute: Attribute,
    *,
    value_option: AttributeValue | None,
    value_bool: bool | None,
    value_number: Decimal | None,
) -> dict[str, str]:
    """Проверяет, что заполнено поле под тип атрибута — и только оно.

    Общая проверка значений атрибута: её делят характеристики товара и
    условия посадочной.
    """
    expected_field = VALUE_FIELD_BY_KIND[Attribute.Kind(attribute.kind)]
    filled = {
        "value_option": value_option is not None,
        "value_bool": value_bool is not None,
        "value_number": value_number is not None,
    }
    errors = {
        field: "Не соответствует типу атрибута."
        for field, is_set in filled.items()
        if is_set and field != expected_field
    }
    if not filled[expected_field]:
        errors[expected_field] = "Заполните значение под тип атрибута."
    if (
        expected_field == "value_option"
        and value_option is not None
        and value_option.attribute_id != attribute.pk
    ):
        errors["value_option"] = "Значение справочника другого атрибута."
    return errors


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
            return BOOL_LABELS[self.value_bool]
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
        errors.update(
            value_kind_errors(
                self.attribute,
                value_option=self.value_option
                if self.value_option_id
                else None,
                value_bool=self.value_bool,
                value_number=self.value_number,
            )
        )
        if errors:
            raise ValidationError(errors)


# Посадочная сужает категорию одним-двумя значениями (ADR-0003):
# длинные хвосты фильтров индексировать незачем
MAX_LANDING_CONDITIONS = 2

# Имя маршрута посадочной: по нему проверяется, что слаг не перекрыл
# уже существующую страницу сайта
LANDING_URL_NAME = "landing"


class LandingQuerySet(models.QuerySet):
    def published(self) -> LandingQuerySet:
        return self.filter(is_published=True)


class Landing(models.Model):
    """Индексируемая страница «категория + значения атрибутов».

    Единственный индексируемый вид фильтрации (ADR-0003): владелец
    заводит её руками под реальный спрос, со своими title/h1/текстом.
    """

    category = models.ForeignKey(
        Category,
        verbose_name="категория",
        on_delete=models.PROTECT,
        related_name="landings",
    )
    slug = models.SlugField("слаг", unique=True, max_length=120)
    title = models.CharField("title страницы", max_length=200)
    heading = models.CharField("заголовок h1", max_length=200)
    description = models.CharField("description", max_length=300)
    text = models.TextField("текст страницы", blank=True)
    is_published = models.BooleanField("опубликована", default=False)
    order = models.PositiveIntegerField("порядок", default=0)

    objects = LandingQuerySet.as_manager()

    class Meta:
        verbose_name = "посадочная"
        verbose_name_plural = "посадочные"
        ordering = ("order", "heading")

    def __str__(self) -> str:
        return self.heading

    def get_absolute_url(self) -> str:
        return reverse(LANDING_URL_NAME, kwargs={"slug": self.slug})

    def clean(self) -> None:
        """Слаг посадочной не должен перекрывать страницу сайта.

        Посадочные живут в корне (`/zerkala-s-podsvetkoy/`), а корень
        делят с «О нас», «Каталогом» и прочими — занятый адрес ловим
        резолвером, чтобы список запретных слов не расходился с urls.py.
        """
        if not self.slug:
            return
        try:
            match = resolve(self.get_absolute_url())
        except Resolver404:
            return
        if match.url_name != LANDING_URL_NAME:
            raise ValidationError(
                {"slug": "Этот адрес уже занят страницей сайта."}
            )


class LandingCondition(models.Model):
    """Одно условие посадочной: значение атрибута её категории.

    Условие — не «фильтр» глоссария: фильтр выбирает посетитель и он не
    индексируется, а условие заводит владелец, и страница с ним как раз
    индексируется (CONTEXT.md, ADR-0003).
    """

    landing = models.ForeignKey(
        Landing,
        verbose_name="посадочная",
        on_delete=models.CASCADE,
        related_name="conditions",
    )
    attribute = models.ForeignKey(
        Attribute,
        verbose_name="атрибут",
        on_delete=models.PROTECT,
        related_name="landing_conditions",
    )
    value_option = models.ForeignKey(
        AttributeValue,
        verbose_name="значение из списка",
        on_delete=models.PROTECT,
        related_name="landing_conditions",
        null=True,
        blank=True,
    )
    value_bool = models.BooleanField("да/нет", null=True, blank=True)

    class Meta:
        verbose_name = "условие посадочной"
        verbose_name_plural = "условия"
        constraints = (
            models.UniqueConstraint(
                fields=("landing", "attribute"),
                name="one_condition_per_landing_attribute",
            ),
        )

    def __str__(self) -> str:
        return f"{self.attribute}: {self.display_value}"

    @property
    def display_value(self) -> str:
        if self.value_option_id:
            return str(self.value_option)
        return BOOL_LABELS[bool(self.value_bool)]

    def clean(self) -> None:
        if not self.attribute_id:
            return
        errors: dict[str, list[str]] = {}
        if self.landing_id and not self.attribute.belongs_to(
            self.landing.category_id
        ):
            errors["attribute"] = ["Атрибут принадлежит другой категории."]
        if self.attribute.kind == Attribute.Kind.NUMBER:
            errors.setdefault("attribute", []).append(
                "Числовым атрибутом посадочную не сузить."
            )
        else:
            for field, message in value_kind_errors(
                self.attribute,
                value_option=self.value_option
                if self.value_option_id
                else None,
                value_bool=self.value_bool,
                value_number=None,
            ).items():
                errors.setdefault(field, []).append(message)
        if errors:
            raise ValidationError(errors)
