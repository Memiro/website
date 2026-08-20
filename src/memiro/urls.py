from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    path(
        "delivery/",
        TemplateView.as_view(template_name="pages/delivery.html"),
        name="delivery",
    ),
    path(
        "contacts/",
        TemplateView.as_view(template_name="pages/contacts.html"),
        name="contacts",
    ),
    path("admin/", admin.site.urls),
    path("", include("memiro.catalog.urls")),
    path("", include("memiro.content.urls")),
    path("", include("memiro.leads.urls")),
    path("", include("memiro.api.urls")),
]

if settings.DEBUG:
    # Медиа (фото товаров) в разработке отдаёт runserver
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
