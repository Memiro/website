from typing import TYPE_CHECKING, ClassVar

from django.contrib import admin
from django.db.models import Prefetch

from .models import Inquiry, InquiryItem

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest


# Имя, под которым `get_queryset` кладёт настроенные позиции, а
# колонка расчёта их читает: связь между ними неявная, и живёт она
# хотя бы в одной строке, а не в двух литералах
CONFIGURED_ITEMS = "configured_items"


class InquiryItemInline(admin.TabularInline):
    model = InquiryItem
    extra = 0
    # Состав — снимок на момент обращения: правке не подлежит.
    # Конфигурация стоит здесь, у своего зеркала, а не над составом:
    # у заявки из двух зеркал размеры разные, и общего поля на них
    # не хватило бы (ADR-0009)
    readonly_fields = (
        "product",
        "product_name",
        "product_price",
        "configuration",
        "calculated_price",
    )
    can_delete = False

    def has_add_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: Inquiry | None = None,  # noqa: ARG002
    ) -> bool:
        return False


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    """Журнал заявок: читается и отмечается обработанной, не создаётся."""

    list_display = (
        "created_at",
        "name",
        "phone",
        "source",
        "calculation",
        "consent",
        "is_processed",
    )
    list_filter = ("source", "is_processed", "created_at")
    list_editable = ("is_processed",)
    search_fields = ("name", "phone", "email", "comment")
    date_hierarchy = "created_at"
    readonly_fields = (
        "name",
        "phone",
        "email",
        "comment",
        "source",
        "consent",
        "consent_version",
        "created_at",
    )
    fields: ClassVar = [
        "created_at",
        "name",
        "phone",
        "email",
        "comment",
        "source",
        "consent",
        "consent_version",
        "is_processed",
    ]
    inlines = (InquiryItemInline,)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Inquiry]:
        """Состав вперёд: колонка расчёта читает его у каждой заявки."""
        return (
            super()
            .get_queryset(request)
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=InquiryItem.objects.exclude(configuration=""),
                    to_attr=CONFIGURED_ITEMS,
                )
            )
        )

    @admin.display(description="расчёт")
    def calculation(self, obj: Inquiry) -> str:
        """Что покупатель настроил и какую цену увидел — в самом списке.

        Менеджер перезванивает, не открывая товар: конфигурации заявки
        и есть весь предмет разговора. Зеркал в заявке бывает
        несколько, и тогда строк тоже несколько — какая из них к
        какому, читается в составе.
        """
        # Пусто, а не падение, если заявку достали мимо `get_queryset`:
        # колонка не то место, где стоит ронять список заявок
        configured: list[InquiryItem] = getattr(obj, CONFIGURED_ITEMS, [])
        lines = [
            f"{item.configuration} — {item.calculated_price_label()}"
            for item in configured
        ]
        return " · ".join(lines) if lines else "—"

    def has_add_permission(self, request: HttpRequest) -> bool:  # noqa: ARG002
        return False
