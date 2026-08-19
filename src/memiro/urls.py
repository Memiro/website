from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path(
        "",
        TemplateView.as_view(template_name="home.html"),
        name="home",
    ),
    path("admin/", admin.site.urls),
    path("", include("memiro.catalog.urls")),
    path("", include("memiro.api.urls")),
]

if settings.DEBUG:
    # Медиа (фото товаров) в разработке отдаёт runserver
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
