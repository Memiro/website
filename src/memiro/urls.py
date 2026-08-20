from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from memiro.catalog.views import landing
from memiro.seo.sitemaps import SITEMAPS
from memiro.seo.views import robots
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    *(
        path(f"{page.route}/", views.static_page(page), name=page.route)
        for page in views.STATIC_PAGES
    ),
    path("admin/", admin.site.urls),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": SITEMAPS},
        name="sitemap",
    ),
    path("robots.txt", robots, name="robots"),
    path("", include("memiro.catalog.urls")),
    path("", include("memiro.content.urls")),
    path("", include("memiro.inquiries.urls")),
    path("", include("memiro.api.urls")),
    # Последним: посадочные живут в корне, и занятые адреса должны
    # достаться настоящим страницам (Landing.clean проверяет это же)
    path("<slug:slug>/", landing, name="landing"),
]

if settings.DEBUG:
    # Медиа (фото товаров) в разработке отдаёт runserver
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
