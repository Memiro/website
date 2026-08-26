import os
from pathlib import Path

# PACKAGE_DIR — каталог пакета memiro: пути внутри пакета (шаблоны)
# должны переживать non-editable установку в site-packages (docker)
PACKAGE_DIR = Path(__file__).resolve().parent

# BASE_DIR — рабочий каталог процесса: сюда кладутся артефакты вне
# пакета (SQLite в разработке, STATIC_ROOT при collectstatic)
BASE_DIR = Path.cwd()

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1",
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "dmr",
    "memiro.catalog",
    "memiro.content",
    "memiro.inquiries",
    "memiro.legal",
    "memiro.seo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Первым в списке — значит последним видит ответ: Vary достаётся
    # и редиректам старых адресов (memiro/legal/middleware.py)
    "memiro.legal.middleware.consent_vary",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Последним: подхватывает 404 и разводит URL старого сайта
    # по 301/410 (тикет 09)
    "memiro.seo.middleware.LegacyUrlMiddleware",
]

# За обратным прокси с терминацией TLS Django видит http и печатает
# такие же canonical, OG и sitemap (тикет 09). Включается там, где
# прокси гарантированно выставляет заголовок сам
if os.environ.get("DJANGO_TRUST_PROXY_SSL") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

ROOT_URLCONF = "memiro.urls"

# Провал проверки CSRF идёт мимо `handler403`: Django зовёт отдельное
# представление и без этой строки рисует свою английскую страницу
# с техническими подсказками (тикет 12)
CSRF_FAILURE_VIEW = "memiro.errors.csrf_failure"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PACKAGE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "memiro.context_processors.contacts",
                "memiro.context_processors.inquiry_limits",
                "memiro.seo.context_processors.defaults",
                "memiro.legal.context_processors.legal",
            ],
        },
    },
]

WSGI_APPLICATION = "memiro.wsgi.application"

# База: SQLite для разработки; PostgreSQL включается наличием
# POSTGRES_HOST в окружении (контуры docker compose и прод)
if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "memiro"),
            "USER": os.environ.get("POSTGRES_USER", "memiro"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        },
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        },
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.NumericPasswordValidator"
        ),
    },
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [PACKAGE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Уведомление менеджера о заявке: транспорт подменяем (тесты ставят свой)
INQUIRY_NOTIFIER = os.environ.get(
    "INQUIRY_NOTIFIER",
    "memiro.inquiries.notifications.EmailNotifier",
)
# Ящик менеджера: пусто — заявка пишется в журнал и в лог, но письма нет
INQUIRY_MANAGER_EMAIL = os.environ.get("INQUIRY_MANAGER_EMAIL", "")

# Отправка письма. Умолчания — под Яндекс.Почту: порт 465 и SSL, а пароль
# приложения вместо пароля от ящика (обычный SMTP не примет). Реквизиты
# живут в окружении, в репозитории их нет.
# Настройка через MAILERS, а не через EMAIL_*: те объявлены устаревшими
# и в Django 7.0 их не станет
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": os.environ.get("EMAIL_HOST", "smtp.yandex.ru"),
            "port": int(os.environ.get("EMAIL_PORT", "465")),
            "username": os.environ.get("EMAIL_HOST_USER", ""),
            "password": os.environ.get("EMAIL_HOST_PASSWORD", ""),
            # 465 у Яндекса — SSL с первого байта, не STARTTLS
            "use_ssl": True,
            # Чужой сервер молчит — заявку это не держит: приём ждёт
            # ответа SMTP ровно столько
            "timeout": 10,
        },
    }
}
# Отправитель по умолчанию — сам ящик: чужой адрес в From Яндекс отвергает
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", os.environ.get("EMAIL_HOST_USER", "")
)

# Единственная аналитика сайта — Яндекс.Метрика, и та за согласием
# (memiro/legal/analytics_consent.py). Пусто — счётчика нет, cookie-баннер
# не показывается: спрашивать не о чем
YANDEX_METRIKA_ID = os.environ.get("YANDEX_METRIKA_ID", "")
