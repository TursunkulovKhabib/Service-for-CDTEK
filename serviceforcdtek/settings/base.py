from .api import *  # noqa: F401,F403
from .celery import *  # noqa: F401,F403
from .companies import *  # noqa: F401,F403
from .env import BASE_DIR, env, env_bool, env_int, env_list
from .ldap import *  # noqa: F401,F403
from .legacy import *  # noqa: F401,F403

SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost;127.0.0.1;0.0.0.0")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    "employees",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "serviceforcdtek.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "serviceforcdtek.wsgi.application"
ASGI_APPLICATION = "serviceforcdtek.asgi.application"

if env("DB_ENGINE", "postgres") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "contacts"),
            "USER": env("POSTGRES_USER", "contacts"),
            "PASSWORD": env("POSTGRES_PASSWORD", "contacts"),
            "HOST": env("POSTGRES_HOST", "127.0.0.1"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", "ru-ru")
TIME_ZONE = env("DJANGO_TIME_ZONE", "Europe/Moscow")
USE_I18N = True
USE_TZ = True
CELERY_TIMEZONE = TIME_ZONE

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

UNFOLD = {
    "SITE_TITLE": "Контакты - справочник сотрудников",
    "SITE_HEADER": "Контакты",
    "SITE_SUBHEADER": "Синхронизация с Active Directory",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SIDEBAR": {"show_search": True, "show_all_applications": True},
}

SENSITIVE_FIELDS = ["bind_password", "password", "token", "secret", "api_key"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "mask_secrets": {"()": "employees.logging_filters.MaskSecretsFilter"},
    },
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["mask_secrets"],
        },
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "ldapsync": {
            "handlers": ["console"],
            "level": env("LDAP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
