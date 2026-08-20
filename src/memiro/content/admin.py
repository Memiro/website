from django.contrib import admin

from .models import Work


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "order")
    list_editable = ("is_published", "order")
    search_fields = ("title",)
