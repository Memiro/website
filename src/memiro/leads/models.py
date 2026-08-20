from django.db import models


class Lead(models.Model):
    """Заявка: обращение посетителя менеджеру (CONTEXT.md).

    Не заказ: оплаты и резервирования нет, дальнейшая сделка живёт
    вне сайта. Состав корзины сохраняется снимком в `LeadItem` —
    цена и название на момент обращения важнее текущих.
    """

    class Source(models.TextChoices):
        HOME = "home", "форма на сайте"
        PRODUCT = "product", "карточка товара"
        CART = "cart", "корзина"

    name = models.CharField("имя", max_length=120)
    phone = models.CharField("телефон", max_length=32)
    email = models.EmailField("e-mail", blank=True)
    comment = models.TextField("комментарий", blank=True)
    source = models.CharField(
        "откуда",
        max_length=10,
        choices=Source.choices,
        default=Source.HOME,
    )
    # Факт согласия на обработку ПД; механика согласий — тикет 10
    consent = models.BooleanField("согласие на обработку ПД", default=False)
    created_at = models.DateTimeField("создана", auto_now_add=True)
    is_processed = models.BooleanField("обработана", default=False)

    class Meta:
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Заявка №{self.pk} — {self.name}, {self.phone}"


class LeadItem(models.Model):
    """Товар в составе заявки — снимком на момент обращения."""

    lead = models.ForeignKey(
        Lead,
        verbose_name="заявка",
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "catalog.Product",
        verbose_name="товар",
        # Заявка переживает удаление товара: снимок остаётся читаемым
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_items",
    )
    product_name = models.CharField("название", max_length=200)
    product_price = models.PositiveIntegerField("цена «от», ₽")

    class Meta:
        verbose_name = "товар заявки"
        verbose_name_plural = "состав заявки"
        ordering = ("pk",)

    def __str__(self) -> str:
        return self.product_name
