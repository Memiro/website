from typing import TYPE_CHECKING, ClassVar

from django.contrib import admin

from .models import Lead, LeadItem

if TYPE_CHECKING:
    from django.http import HttpRequest


class LeadItemInline(admin.TabularInline):
    model = LeadItem
    extra = 0
    # Состав — снимок на момент обращения: правке не подлежит
    readonly_fields = ("product", "product_name", "product_price")
    can_delete = False

    def has_add_permission(
        self,
        request: HttpRequest,  # noqa: ARG002
        obj: Lead | None = None,  # noqa: ARG002
    ) -> bool:
        return False


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """Журнал заявок: читается и отмечается обработанной, не создаётся."""

    list_display = (
        "created_at",
        "name",
        "phone",
        "source",
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
        "is_processed",
    ]
    inlines = (LeadItemInline,)

    def has_add_permission(self, request: HttpRequest) -> bool:  # noqa: ARG002
        return False
