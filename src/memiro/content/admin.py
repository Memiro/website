from typing import ClassVar

from django.contrib import admin

from .models import FaqEntry, Promo, Review, Work


class PublishedAdmin(admin.ModelAdmin):
    """Общий раздел контента: публикация и порядок правятся списком."""

    list_editable = ("is_published", "order")
    list_filter: ClassVar[tuple[str, ...]] = ("is_published",)


@admin.register(Work)
class WorkAdmin(PublishedAdmin):
    list_display = ("title", "is_published", "order")
    search_fields = ("title",)


@admin.register(Review)
class ReviewAdmin(PublishedAdmin):
    list_display = ("author", "source", "rating", "is_published", "order")
    list_filter = ("is_published", "source")
    search_fields = ("author", "text")


@admin.register(FaqEntry)
class FaqEntryAdmin(PublishedAdmin):
    list_display = ("question", "is_published", "order")
    search_fields = ("question", "answer")


@admin.register(Promo)
class PromoAdmin(PublishedAdmin):
    list_display = ("title", "is_published", "order")
    search_fields = ("title", "text")
    # Блок на главной один: какая из акций в него попадёт — видно в форме
    fieldsets = (
        (
            None,
            {
                "fields": ("title", "text", "is_published", "order"),
                "description": (
                    "На главную выходит первая опубликованная акция "
                    "по полю «порядок». Товары в её ленту набираются "
                    "флагом «акция» в карточке товара."
                ),
            },
        ),
    )
