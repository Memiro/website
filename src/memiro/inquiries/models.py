from django.db import models


class Inquiry(models.Model):
    """Заявка: обращение посетителя менеджеру (CONTEXT.md).

    Не заказ: оплаты и резервирования нет, дальнейшая сделка живёт
    вне сайта. Состав корзины сохраняется снимком в `InquiryItem` —
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
    # Факт согласия на обработку ПД: без него заявка не принимается
    consent = models.BooleanField("согласие на обработку ПД", default=False)
    # Редакция текста согласия, с которой человек согласился. Ставит
    # сервер из `legal.privacy.PRIVACY_VERSION` — клиент на неё
    # не влияет, иначе это не доказательство
    consent_version = models.CharField(
        "редакция согласия",
        max_length=20,
        blank=True,
    )
    # Что покупатель посчитал в калькуляторе, когда оставлял заявку:
    # габариты и выбранные им значения одной читаемой строкой. Снимок,
    # как название и цена товара в составе: справочник переименуют,
    # а прочитать заявку менеджер должен и через год. Пусто — расчёта
    # не было: заявка из корзины, свободной формой или с карточки
    # без калькулятора
    configuration = models.TextField("конфигурация расчёта", blank=True)
    # Цена, которую сайт показал на этой конфигурации. Ставит её
    # сервер, пересчитывая присланное теми же тарифами, что и
    # витрина, — цена, присланная браузером, доказательством в споре
    # не была бы (тикет 21). Пусто и при расчёте: размеру за пределом
    # производства цены не называют вовсе, но конфигурация менеджеру
    # нужна и там — это и есть личное пожелание
    calculated_price = models.PositiveIntegerField(
        "посчитанная цена, ₽", null=True, blank=True
    )
    created_at = models.DateTimeField("создана", auto_now_add=True)
    is_processed = models.BooleanField("обработана", default=False)

    class Meta:
        verbose_name = "заявка"
        verbose_name_plural = "заявки"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Заявка №{self.pk} — {self.name}, {self.phone}"


class InquiryItem(models.Model):
    """Товар в составе заявки — снимком на момент обращения."""

    inquiry = models.ForeignKey(
        Inquiry,
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
        related_name="inquiry_items",
    )
    product_name = models.CharField("название", max_length=200)
    # Снимок цены на момент заявки; пусто — у товара её не было
    # вовсе, вариантов ему не завели (ADR-0007)
    product_price = models.PositiveIntegerField(
        "цена «от», ₽", null=True, blank=True
    )

    class Meta:
        verbose_name = "товар заявки"
        verbose_name_plural = "состав заявки"
        ordering = ("pk",)

    def __str__(self) -> str:
        return self.product_name
