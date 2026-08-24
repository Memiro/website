from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import Resolver404, resolve, reverse

from memiro import pricing

if TYPE_CHECKING:
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
    # Кнопки не бывает без подсветки или подогрева (ADR-0007). Родителей
    # несколько именно поэтому: условие «или», а не «и» — товару хватает
    # одного из них. Пусто — атрибут самостоятелен
    parents = models.ManyToManyField(
        "self",
        verbose_name="существует только при",
        symmetrical=False,
        related_name="children",
        blank=True,
    )
    # Тип полотна, подогрев и крепление покупатель меняет в калькуляторе;
    # подсветка, рама и форма описывают модель. В расчёт входят и те,
    # и другие — признак говорит лишь, кто их выбирает
    is_customer_editable = models.BooleanField(
        "меняет покупатель",
        default=False,
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

    def depends_on(self, other: Attribute) -> bool:
        """Атрибут опирается на другой — прямо или через цепочку."""
        seen: set[int] = set()
        queue = list(self.parents.all())
        while queue:
            parent = queue.pop()
            if parent.pk == other.pk:
                return True
            if parent.pk in seen:
                continue
            seen.add(parent.pk)
            queue.extend(parent.parents.all())
        return False

    def missing_parent_error(
        self, present_attribute_ids: set[int]
    ) -> str | None:
        """Объясняет, почему атрибут здесь осиротел, — или молчит.

        Набор атрибутов товара известен целиком только там, где
        сохраняется товар: родителя и ребёнка владелец заводит одним
        сохранением, и по одной строке судить нельзя.
        """
        parents = list(self.parents.all())
        if not parents:
            return None
        if {parent.pk for parent in parents} & present_attribute_ids:
            return None
        names = ", ".join(f"«{parent.name}»" for parent in parents)
        return (
            f"«{self.name}» существует только при: {names} — "
            "задайте у товара хотя бы один из них."
        )

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
    """Значение из справочника атрибута типа «выбор из списка».

    Оно же — строка тарифа (ADR-0007): единица, в которой значение
    расходуется, и ставка. Отдельной модели тарифов нет, чтобы владелец
    не заводил подсветку дважды.
    """

    # Значения — из движка цены: разошедшись, админка и расчёт молча
    # перестали бы понимать друг друга
    class Unit(models.TextChoices):
        PIECE = pricing.Unit.PIECE.value, "за штуку"
        LINEAR_METER = pricing.Unit.LINEAR_METER.value, "за погонный метр"
        SQUARE_METER = pricing.Unit.SQUARE_METER.value, "за квадратный метр"
        FACTOR = pricing.Unit.FACTOR.value, "коэффициент"

    attribute = models.ForeignKey(
        Attribute,
        verbose_name="атрибут",
        on_delete=models.CASCADE,
        related_name="values",
    )
    value = models.CharField("значение", max_length=100)
    # Пустая единица со ставкой None — «бесплатно»: значение описывает
    # товар, но денег не стоит (цвет рамы). Так же выглядят 425 значений,
    # переехавших со старого сайта до заведения тарифов
    unit = models.CharField(
        "единица расхода",
        max_length=12,
        choices=Unit.choices,
        blank=True,
    )
    rate = models.DecimalField(
        "тариф",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal(0))],
        help_text="Рубли за единицу; для коэффициента — множитель.",
    )
    # Коэффициент формы умножает то, что режется по контуру, — полотно и
    # обработку кромки. Контурная лента меряется тем же погонным метром,
    # но на криволинейном резе дороже не становится, и одной единицей
    # расхода эти два случая не различить (ADR-0007, тикет 16)
    scaled_by_shape = models.BooleanField(
        "умножается коэффициентом формы",
        default=False,
    )
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

    @property
    def full_label(self) -> str:
        """Значение с названием атрибута: «Тип полотна: Серебро».

        Одним словом «Серебро» не понять, полотно это или рама. Так
        значение подписано и в списке варианта в админке, и в строке
        разложения цены, из которой эндпоинт расчёта соберёт подписи
        доплат покупателю.
        """
        return f"{self.attribute.name}: {self.value}"

    def clean(self) -> None:
        """Тариф — пара: половина ставки молча считалась бы нулём."""
        if self.scaled_by_shape and self.unit in {"", self.Unit.FACTOR}:
            message = (
                "Коэффициент формы умножает статью расхода — "
                "у бесплатного значения и у самого коэффициента её нет."
            )
            raise ValidationError({"scaled_by_shape": message})
        if bool(self.unit) == (self.rate is not None):
            return
        field, message = (
            ("rate", "Укажите ставку — с единицей расхода она обязательна.")
            if self.unit
            else ("unit", "Укажите единицу расхода: ставка без неё не тариф.")
        )
        raise ValidationError({field: message})


class PricingSettings(models.Model):
    """Параметры расчёта: минимальная площадь и минимальная сумма заказа.

    Данные, а не константы в коде (ADR-0007): маленькое зеркало считается
    по минимальной площади, а итог не опускается ниже минимальной суммы —
    оба порога владелец меняет сам. Строка одна на сайт.
    """

    SINGLETON_PK = 1

    # 0,25 м² — обычная минимальная площадь обработки у стекольных
    # производств; владелец правит под свою
    min_area_m2 = models.DecimalField(
        "минимальная площадь расчёта, м²",
        max_digits=5,
        decimal_places=3,
        default=Decimal("0.250"),
        validators=[MinValueValidator(Decimal(0))],
    )
    min_order_total = models.PositiveIntegerField(
        "минимальная сумма заказа, ₽",
        default=0,
    )
    # Верхние пределы: изделие крупнее производство не берёт, и цены
    # ему сайт не называет — это личное пожелание, и оно уходит
    # заявкой (ADR-0007). Сторонами, а не площадью: режут из листа.
    # Ноль — «без предела»: свои цифры владелец знает сам, а выдумать
    # их за него значило бы однажды отказать в считаемом размере
    max_long_side_mm = models.PositiveIntegerField(
        "наибольшая сторона изделия, мм",
        default=0,
        help_text="0 — предела нет. Изделие поворачивают: сверяется "
        "длинная сторона с этим пределом, короткая — со следующим.",
    )
    max_short_side_mm = models.PositiveIntegerField(
        "вторая сторона изделия, мм",
        default=0,
    )

    class Meta:
        verbose_name = "параметры расчёта"
        verbose_name_plural = "параметры расчёта"

    def __str__(self) -> str:
        return "Параметры расчёта"

    def save(self, *args: object, **kwargs: object) -> None:
        """Строка всегда одна: второй набор порогов — вторая правда."""
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def clean(self) -> None:
        """Короткий предел длиннее длинного — не предел, а опечатка.

        Сверка идёт длинной стороной к длинному пределу; будь второй
        больше первого, часть его так и осталась бы недосягаемой.
        """
        if 0 < self.max_long_side_mm < self.max_short_side_mm:
            message = (
                "Вторая сторона не может быть больше наибольшей — "
                "сверка идёт длинной стороной изделия."
            )
            raise ValidationError({"max_short_side_mm": message})


# Витринный порядок «сначала популярные»: один кортеж на весь проект
POPULAR_ORDERING = ("-is_popular", "order", "name")


class ProductQuerySet(models.QuerySet):
    def published(self) -> ProductQuerySet:
        return self.filter(is_published=True)

    def by_popularity(self) -> ProductQuerySet:
        return self.order_by(*POPULAR_ORDERING)


class Product(models.Model):
    """Изделие под заказ; наличия нет, цена — из вариантов (CONTEXT.md)."""

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
    # Не то, что вводит владелец, а то, что пересчитывается из его
    # предпосчитанных вариантов (`catalog.repricing`): «от X ₽» — цена
    # самого дешёвого. NULL значит «вариантов нет», и тогда товар цены
    # не показывает вовсе — это честнее заглушки. Полем, а не
    # вычисляемым свойством, цена остаётся намеренно (ADR-0007): на ней
    # держатся фильтр диапазона, сортировка, мета категории, lowPrice
    # в разметке и снимок цены в заявке
    price = models.PositiveIntegerField(
        "цена «от», ₽",
        null=True,
        editable=False,
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
    def has_price(self) -> bool:
        """Есть ли у товара цена — один ответ на всю витрину.

        `is not None`, а не истинность поля. Ноль расчёт вернуть может:
        изделие, у которого не набралось ни одной платной статьи, —
        значит, тарифы завели не до конца. Но варианты у такого товара
        есть, и таблица на карточке напечатает их «0 ₽» в любом случае;
        спрячь при этом «от», и страница покажет цены там, где цены
        якобы нет. Ноль — заметная неправильная цена, и пусть она будет
        видна владельцу, а не спрятана от него.
        """
        return self.price is not None

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


# Габариты варианта в подписи: «800 × 600 мм»
SIZE_SEPARATOR = " × "


class ProductVariant(models.Model):
    """Предпосчитанный вариант: размеры плюс значения атрибутов.

    Точка расчёта, а не товар (CONTEXT.md): своего адреса, фото и места
    в каталоге у варианта нет, в sitemap он не попадает.

    Цену владелец не вводит — её считает движок из тех же тарифов, что
    и калькулятор (`catalog.repricing`), иначе таблица на карточке и
    расчёт разошлись бы на одних и тех же параметрах.
    """

    product = models.ForeignKey(
        Product,
        verbose_name="товар",
        on_delete=models.CASCADE,
        related_name="variants",
    )
    width_mm = models.PositiveIntegerField(
        "ширина, мм",
        validators=[MinValueValidator(1)],
    )
    height_mm = models.PositiveIntegerField(
        "высота, мм",
        validators=[MinValueValidator(1)],
    )
    # Чем вариант отличается от умолчаний товара: полотно, крепление,
    # подогрев. Значения атрибутов, которых здесь нет, вариант берёт
    # у товара. Через-модели у связи нет намеренно: вложенный инлайн
    # админка не умеет, а варианты правятся в карточке товара
    values = models.ManyToManyField(
        AttributeValue,
        verbose_name="значения атрибутов",
        related_name="variant_selections",
        blank=True,
    )
    # editable=False: поле не попадает ни в одну форму — ни в админскую,
    # ни в чью-либо ещё. Пересчёт живёт в `catalog.repricing`
    price = models.PositiveIntegerField("цена, ₽", default=0, editable=False)
    order = models.PositiveIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "предпосчитанный вариант"
        verbose_name_plural = "предпосчитанные варианты"
        ordering = ("order", "pk")

    def __str__(self) -> str:
        return f"{self.size_label} — {self.product}"

    @property
    def size_label(self) -> str:
        """Габариты строкой — так размер и печатается на карточке."""
        return f"{self.width_mm}{SIZE_SEPARATOR}{self.height_mm} мм"

    @property
    def values_label(self) -> str:
        """Чем вариант отличается от умолчаний товара — одной строкой.

        Без названий атрибутов, в отличие от `AttributeValue.full_label`:
        покупатель смотрит на зеркало и читает «Серебро», а не
        «Тип полотна: Серебро».
        """
        return ", ".join(str(value) for value in self.values.all())


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
    # Кадр для плитки витрины. Пустое поле — плитка берёт фото первого
    # товара посадочной, но выбор кадра остаётся за владельцем
    cover = models.ImageField(
        "обложка плитки",
        upload_to="landings/",
        blank=True,
    )
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
