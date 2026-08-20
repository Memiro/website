from django.urls import path

from . import views

urlpatterns = [
    path("works/", views.works, name="works"),
]
