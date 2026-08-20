from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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


# Пять звёзд — потолок шкалы; тот же максимум ждёт разметка рейтинга
MAX_RATING = 5


class Review(PublishedContent):
    """Настоящий отзыв клиента, занесённый вручную (CONTEXT.md).

    Источник обязателен: отзывы переносятся с площадок (например Avito),
    и в разметку рейтинга (тикет 09) попадают только реальные записи.
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
        """Оценка звёздами — шаблону нечего считать самому."""
        return "★" * self.rating + "☆" * (MAX_RATING - self.rating)

    @property
    def rating_label(self) -> str:
        """Та же оценка словами: звёзды читалке экрана ничего не говорят."""
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
    """Маркетинговое предложение, публикуемое владельцем (CONTEXT.md).

    На главной акция задаёт заголовок блока со специальными ценами;
    товары в него набираются флагом «акция» у товара (тикет 03).
    """

    title = models.CharField("заголовок", max_length=200)
    text = models.TextField("описание", blank=True)

    class Meta(PublishedContent.Meta):
        verbose_name = "акция"
        verbose_name_plural = "акции"

    def __str__(self) -> str:
        return self.title
