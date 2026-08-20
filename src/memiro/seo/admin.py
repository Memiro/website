from django.contrib import admin

from .models import LegacyUrl


@admin.register(LegacyUrl)
class LegacyUrlAdmin(admin.ModelAdmin):
    list_display = ("old_path", "new_path", "note")
    search_fields = ("old_path", "new_path", "note")
