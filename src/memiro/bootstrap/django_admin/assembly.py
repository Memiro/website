from functools import partial
from typing import Any

from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.di.container import get_async_container
from memiro.presentation.django_admin.bridge import CONTAINER_FACTORY_SETTING


def admin_settings(config: Config) -> dict[str, Any]:
    """Turn the context's configuration into the names Django reads as settings."""
    return {
        "SECRET_KEY": config.admin.secret_key,
        "DEBUG": False,
        # Logging is already configured by the settings module: Django must
        # not run its own dictConfig over it and take the root handler away.
        "LOGGING_CONFIG": None,
        "ALLOWED_HOSTS": list(config.admin.allowed_hosts),
        "INSTALLED_APPS": [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.messages",
            "django.contrib.sessions",
            "django.contrib.staticfiles",
            "django.contrib.postgres",
            "memiro.presentation.django_admin",
        ],
        "MIDDLEWARE": [
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ],
        "ROOT_URLCONF": "memiro.bootstrap.django_admin.urls",
        "WSGI_APPLICATION": "memiro.bootstrap.django_admin.wsgi.application",
        "TEMPLATES": [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True,
                "DIRS": [],
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            },
        ],
        # The synchronous driver: the admin is WSGI, and only the async
        # interactors behind the bridge speak asyncpg.
        "DATABASES": {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": config.db.host,
                "PORT": config.db.port,
                "USER": config.db.user,
                "PASSWORD": config.db.password,
                "NAME": config.db.database,
            },
        },
        # The bridge assembles the container from this factory inside its own
        # loop; the admin package never reaches into the bootstrap itself.
        CONTAINER_FACTORY_SETTING: partial(get_async_container, config),
        "DEFAULT_AUTO_FIELD": "django.db.models.BigAutoField",
        "LANGUAGE_CODE": "ru-ru",
        "TIME_ZONE": "Europe/Moscow",
        "USE_I18N": True,
        "USE_TZ": True,
        # Django's own prefix would collide with the admin's URLs; nginx
        # serves this one from the directory collectstatic fills.
        "STATIC_URL": "/admin-static/",
        # The photos themselves are served by nginx off the media volume; the
        # admin only ever prints their address.
        "MEDIA_URL": "/media/",
        "STATIC_ROOT": config.admin.static_root,
        # nginx is the edge and terminates TLS; the admin never sees the
        # scheme itself.
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SESSION_COOKIE_HTTPONLY": True,
        "CSRF_COOKIE_HTTPONLY": True,
        "X_FRAME_OPTIONS": "DENY",
    }
