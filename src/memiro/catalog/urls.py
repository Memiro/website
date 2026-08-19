from django.urls import path

from . import views

urlpatterns = [
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<slug:slug>/", views.category, name="category"),
    path(
        "catalog/<slug:category_slug>/<slug:slug>/",
        views.product,
        name="product",
    ),
]
