import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = env(name, "").strip()
    return int(raw) if raw else default


def env_list(name: str, default: str = "", sep: str = ";") -> list:
    raw = env(name, default)
    return [item.strip() for item in raw.split(sep) if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
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
    "django_filters",
    "django_celery_beat",
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

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LDAP = {
    "PROFILE": env("LDAP_PROFILE", "ad"),
    "SERVER_URI": env("LDAP_SERVER_URI", "ldaps://dc01.example.local"),
    "PORT": env_int("LDAP_PORT", 0) or None,
    "USE_SSL": env_bool("LDAP_USE_SSL", True),
    "START_TLS": env_bool("LDAP_START_TLS", False),
    "TLS_VALIDATE": env_bool("LDAP_TLS_VALIDATE", True),
    "CA_CERTS_FILE": env("LDAP_CA_CERTS_FILE", "") or None,
    "BIND_DN": env("LDAP_BIND_DN", ""),
    "BIND_PASSWORD": env("LDAP_BIND_PASSWORD", ""),
    "AUTHENTICATION": env("LDAP_AUTHENTICATION", "SIMPLE"),
    "BASE_DN": env("LDAP_BASE_DN", "DC=example,DC=local"),
    "SEARCH_OUS": env_list("LDAP_SEARCH_OUS", ""),
    "USER_FILTER": env("LDAP_USER_FILTER", ""),
    "INCLUDE_DISABLED": env_bool("LDAP_INCLUDE_DISABLED", False),
    "PAGE_SIZE": env_int("LDAP_PAGE_SIZE", 500),
    "TIMEOUT": env_int("LDAP_TIMEOUT", 30),
    "RECEIVE_TIMEOUT": env_int("LDAP_RECEIVE_TIMEOUT", 60),
    "DEACTIVATE_MISSING": env_bool("LDAP_DEACTIVATE_MISSING", True),
    "MIN_ENTRIES_FOR_DEACTIVATION": env_int("LDAP_MIN_ENTRIES_FOR_DEACTIVATION", 1),
}

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": env_int("API_PAGE_SIZE", 50),
    "DEFAULT_PERMISSION_CLASSES": ["employees.permissions.HasAPIKeyOrIsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
}

API_KEY = env("API_KEY", "")
API_REQUIRE_KEY = env_bool("API_REQUIRE_KEY", not DEBUG)

CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 60 * 30)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
LDAP_SYNC_INCREMENTAL_MINUTES = env_int("LDAP_SYNC_INCREMENTAL_MINUTES", 15)
LDAP_SYNC_FULL_CRON = env("LDAP_SYNC_FULL_CRON", "20 3 * * *")

UNFOLD = {
    "SITE_TITLE": "Контакты - справочник сотрудников",
    "SITE_HEADER": "Контакты",
    "SITE_SUBHEADER": "Синхронизация с Active Directory",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
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
