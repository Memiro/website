from django.contrib import admin
from django.urls import URLPattern, URLResolver, path

# The prefix is kept end to end: nginx proxies /admin/ without rewriting it.
urlpatterns: list[URLPattern | URLResolver] = [path("admin/", admin.site.urls)]
