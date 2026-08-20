from django.db import models


class WorkQuerySet(models.QuerySet):
    def published(self) -> WorkQuerySet:
        return self.filter(is_published=True)


class Work(models.Model):
    """Фото реальной установки изделия у клиента (CONTEXT.md)."""

    title = models.CharField("подпись", max_length=200)
    image = models.ImageField("фото", upload_to="works/")
    is_published = models.BooleanField("опубликована", default=False)
    order = models.PositiveIntegerField("порядок", default=0)

    objects = WorkQuerySet.as_manager()

    class Meta:
        verbose_name = "работа"
        verbose_name_plural = "наши работы"
        ordering = ("order", "pk")

    def __str__(self) -> str:
        return self.title
