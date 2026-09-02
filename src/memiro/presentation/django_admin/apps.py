from django.apps import AppConfig


class DjangoAdminConfig(AppConfig):
    """The admin presentation of the ``memiro`` context (ADR-0012)."""

    name = "memiro.presentation.django_admin"
    label = "memiro"
    verbose_name = "Memiro"
