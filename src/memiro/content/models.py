from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from memiro.singleton import SingletonModel


class PublishedQuerySet(models.QuerySet):
    """Общая выборка для контента, который владелец публикует и скрывает."""

    def published(self) -> PublishedQuerySet:
        return self.filter(is_published=True)


class PublishedContent(models.Model):
    """Запись контента: владелец публикует её и задаёт порядок.

    Одна форма на все разделы админки — новый раздел не переписывает
    флаг публикации и сортировку заново.
    """

    is_published = models.BooleanField("опубликовано", default=False)
    order = models.PositiveIntegerField("порядок", default=0)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ("order", "pk")


class Work(PublishedContent):
    """Фото реальной установки изделия у клиента (CONTEXT.md)."""

    title = models.CharField("подпись", max_length=200)
    image = models.ImageField("фото", upload_to="works/")

    class Meta(PublishedContent.Meta):
        verbose_name = "работа"
        verbose_name_plural = "наши работы"

    def __str__(self) -> str:
        return self.title


# Пять звёзд — потолок шкалы: и для валидатора оценки, и для звёзд,
# которыми отзыв вернётся на витрину
MAX_RATING = 5


class Review(PublishedContent):
    """Настоящий отзыв клиента, занесённый вручную (CONTEXT.md).

    Источник обязателен: отзывы переносятся с площадок (например Avito),
    и настоящими они остаются даже сейчас, когда витрина их не
    показывает (тикет 06 набора `owner-revision`) — вместе с блоком
    ушла и разметка рейтинга.
    """

    author = models.CharField("автор", max_length=120)
    text = models.TextField("текст")
    # Свободный текст, а не справочник: новая площадка не должна ждать
    # разработчика — это тот же принцип, что у атрибутов (ADR-0002)
    source = models.CharField("источник", max_length=60)
    source_url = models.URLField("ссылка на источник", blank=True)
    rating = models.PositiveSmallIntegerField(
        "оценка",
        default=MAX_RATING,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_RATING)],
    )
    avatar = models.ImageField(
        "фото автора",
        upload_to="reviews/",
        blank=True,
    )

    class Meta(PublishedContent.Meta):
        verbose_name = "отзыв"
        verbose_name_plural = "отзывы"

    def __str__(self) -> str:
        return f"{self.author} ({self.source})"

    @property
    def stars(self) -> str:
        """Оценка звёздами — считает модель, не шаблон.

        Носителя у неё сейчас нет: блок отзывов снят с витрины
        (тикет 06 набора `owner-revision`). Оставлена вместе с моделью
        — вернётся тем же тикетом, что и блок.
        """
        return "★" * self.rating + "☆" * (MAX_RATING - self.rating)

    @property
    def rating_label(self) -> str:
        """Та же оценка словами: звёзды читалке экрана ничего не говорят.

        Как и `stars`, ждёт возвращения блока отзывов на витрину.
        """
        return f"Оценка: {self.rating} из {MAX_RATING}"


class FaqEntry(PublishedContent):
    """Вопрос и ответ из админки; выводится списком на главной."""

    question = models.CharField("вопрос", max_length=200)
    answer = models.TextField("ответ")

    class Meta(PublishedContent.Meta):
        verbose_name = "вопрос и ответ"
        verbose_name_plural = "вопросы и ответы"

    def __str__(self) -> str:
        return self.question


class Promo(PublishedContent):
    """Маркетинговое предложение, заводимое владельцем (CONTEXT.md).

    На витрину не выходит: блок снят с главной вместе с бейджем
    «Акция» у товара (тикет 05). Модель осталась потому, что скрытие
    временное — акции вернутся, называя размер скидки.
    """

    title = models.CharField("заголовок", max_length=200)
    text = models.TextField("описание", blank=True)

    class Meta(PublishedContent.Meta):
        verbose_name = "акция"
        verbose_name_plural = "акции"

    def __str__(self) -> str:
        return self.title


class SiteContacts(SingletonModel):
    """Контакты студии: адрес, связь, часы, карта. Строка одна на сайт.

    Данные владельца, а не константы в коде (тот же принцип, что
    у атрибутов — ADR-0002 — и у порогов расчёта — ADR-0007): адрес
    шоурума меняется чаще, чем выходит релиз.

    Телефон, почта и адрес обязательны — без них витрины не бывает.
    Ссылки и карта заводятся по желанию, и пустая значит «не
    показывать»: витрина не рисует иконку в никуда, разметка
    не называет профиль.
    """

    # Город и улица — раздельно: разметке LocalBusiness они нужны
    # порознь, витрине — одной строкой (свойство `address`)
    city = models.CharField("город", max_length=120)
    street = models.CharField("улица и дом", max_length=200)
    phone = models.CharField(
        "телефон для ссылки",
        max_length=20,
        help_text="Как в tel:, без пробелов и скобок: +79812304050",
    )
    phone_display = models.CharField(
        "телефон как показывать",
        max_length=30,
        help_text="Как читает человек: +7 981 230-40-50",
    )
    email = models.EmailField("e-mail")
    hours = models.CharField(
        "часы работы",
        max_length=200,
        help_text="Строка для человека: «Ежедневно, по предварительной "
        "записи»",
    )
    # Часы для разметки: витрина говорит человеку «по записи», а
    # поисковику нужны границы. Пока не заданы оба — разметка о часах
    # молчит: выдуманное расписание такое же враньё, как незаполненный
    # контакт. Время, а не строка: «25:99» до поисковика не доедет
    opens = models.TimeField(
        "открытие для разметки",
        null=True,
        blank=True,
        help_text="Пока открытие и закрытие не заданы оба, "
        "сайт о расписании молчит.",
    )
    closes = models.TimeField("закрытие для разметки", null=True, blank=True)
    # Связь со студией — телефон, почта и MAX (решение владельца,
    # тикет 08). Труба, по которой заявка едет менеджеру, к этому полю
    # отношения не имеет. `max_link`, а не `max` в ряд к `vk` и `avito`:
    # имя встроенной функции в атрибуте класса линтер читает как ошибку
    max_link = models.URLField(
        "MAX",
        blank=True,
        help_text="Пока стоит заглушка: настоящий адрес владелец "
        "подставит сюда сам, без выкатки.",
    )
    vk = models.URLField("ВКонтакте", blank=True)
    avito = models.URLField(
        "витрина на Avito",
        blank=True,
        help_text="Витрина студии на Avito. Сейчас ссылку видят только "
        "поисковики: блок отзывов, из которого вела «Смотреть все», снят.",
    )
    map_embed = models.URLField(
        "карта шоурума",
        max_length=500,
        blank=True,
        help_text="Ссылка виджета Яндекс.Карт. Пустая — карты "
        "на «Контактах» не будет.",
    )

    class Meta:
        verbose_name = "контакты студии"
        verbose_name_plural = "контакты студии"

    def __str__(self) -> str:
        return "Контакты студии"

    def clean(self) -> None:
        """Одна граница расписания — не расписание, а полдела.

        Разметка молчит о часах, пока не заданы обе, и заполненное
        в одиночку поле молча пропало бы.
        """
        if bool(self.opens) != bool(self.closes):
            message = (
                "Часы для разметки задаются парой: и открытие, "
                "и закрытие — иначе сайт о расписании промолчит."
            )
            raise ValidationError({"opens": message, "closes": message})

    @property
    def address(self) -> str:
        """Адрес одной строкой — витрине незачем склеивать самой."""
        return ", ".join(part for part in (self.city, self.street) if part)

    @property
    def has_schedule(self) -> bool:
        """Обе границы заданы — разметке есть что сказать о часах."""
        return bool(self.opens and self.closes)
