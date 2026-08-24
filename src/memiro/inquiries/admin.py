from typing import TYPE_CHECKING, ClassVar

from django.contrib import admin

from memiro.catalog.formatting import rub
from .models import Inquiry, InquiryItem

if TYPE_CHECKING:
    from django.http import HttpRequest


class InquiryItemInline(admin.TabularInline):
    model = InquiryItem
    extra = 0
    # Состав — снимок на момент обращения: правке не подлежит
    readonly_fields = ("product", "product_name", "product_price")
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
        "configuration",
        "calculated_price",
        "created_at",
    )
    fields: ClassVar = [
        "created_at",
        "name",
        "phone",
        "email",
        "comment",
        "source",
        "configuration",
        "calculated_price",
        "consent",
        "consent_version",
        "is_processed",
    ]
    inlines = (InquiryItemInline,)

    @admin.display(description="расчёт")
    def calculation(self, obj: Inquiry) -> str:
        """Что покупатель считал и какую цену увидел — прямо в журнале.

        Менеджер перезванивает, не открывая товар: конфигурация в
        заявке и есть весь предмет разговора. Цены может не быть при
        конфигурации — размеру за пределом производства сайт цены не
        называет, и это личное пожелание, а не пробел.
        """
        if not obj.configuration:
            return "—"
        price = (
            f"{rub(obj.calculated_price)} ₽"
            if obj.calculated_price is not None
            else "цена не рассчитана"
        )
        return f"{obj.configuration} — {price}"

    def has_add_permission(self, request: HttpRequest) -> bool:  # noqa: ARG002
        return False
