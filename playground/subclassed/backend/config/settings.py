"""Subclassed-host playground settings — Phase 8, docs/APP-DESIGN.md §11.2.

Same two-half structure as ../../default/backend/config/settings.py — read that file's own
docstring for the full "HOST BASELINE" vs. "DYNAMIC_USER WIRING" rationale, not repeated here.

The one thing that actually differs from the default host, model-wise: **every top-level
swappable setting points at `core`, this host's own app, not `dynamic_user`'s concrete models** —
`core.User`/`core.Profile`/`core.Setting` (see `core/models.py`). This is the entire point of this
host: proving a subclass with one extra field per model needs no package-level code change, only
this settings file and `core/`.

The two postures deliberately differ from the default host too, so both are live and comparable
without a restart: `ADMIN_REQUIRES_SUPERUSER=True` here (vs. `False` there) and
`DELETION_MODE="anonymize"` here (vs. `"hard_delete"` there).
"""

from __future__ import annotations

from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================================================
# HOST BASELINE — what a fresh Django host already has before any app package is installed.
# ============================================================================================

SECRET_KEY = config("SECRET_KEY", default="playground-not-a-secret")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS", default="localhost,127.0.0.1,backend-subclassed", cast=lambda v: v.split(",")
)

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",  # mandatory — dynamic_user.ChangeLogEntry FKs it
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "appkit",
    # `core` — the host's own app, per docs/INTEGRATION-GUIDE.md §4's convention. Its
    # models.py subclasses AbstractDynamicUser/AbstractProfile/AbstractSetting; it must be
    # installed BEFORE "dynamic_user" is added below, or Django's swappable-model resolution
    # can't find it at migration time.
    "core",
    # ---- DYNAMIC_USER WIRING adds "dynamic_user" below ----
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "appkit.request_id.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="playground_subclassed"),
        "USER": config("POSTGRES_USER", default="playground"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="playground"),
        "HOST": config("POSTGRES_HOST", default="db"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

# Redis DB index 1, not 0 — this host shares the same Redis service as the default host
# (playground/docker-compose.yml) but must not share cache keys with it.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://redis:6379/1"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:3001",
    cast=lambda v: v.split(","),
)

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

REST_FRAMEWORK: dict[str, object] = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "appkit.pagination.DefaultPagination",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "NUM_PROXIES": 0,
    "DEFAULT_THROTTLE_RATES": {},
}

APPKIT = {
    "TRUSTED_PROXY_COUNT": 0,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "django-dynamic-user playground — subclassed host",
    "VERSION": "0.1.0",
    "COMPONENT_SPLIT_REQUEST": True,
}

JAZZMIN_SETTINGS = {
    "site_title": "dynamic_user playground",
    "site_header": "Playground (subclassed)",
    "site_brand": "django-dynamic-user",
    "welcome_sign": "Dynamic User Playground — subclassed models (core.User/Profile/Setting)",
    # Same suggested icons as the default host, keyed to "core" instead of "dynamic_user" — a
    # host subclassing the models must re-key these itself; that's the live check.
    "icons": {
        "core.user": "fas fa-user",
        "core.profile": "fas fa-id-card",
        "core.setting": "fas fa-sliders-h",
        "dynamic_user.accountdeletionrequest": "fas fa-user-slash",  # not swappable — unchanged
        "dynamic_user.changelogentry": "fas fa-history",  # not swappable — unchanged
    },
}

# ============================================================================================
# DYNAMIC_USER WIRING — same throttle-scope block as the default host (docs/CONTRACT.md §5); the
# DYNAMIC_USER dict itself differs, and is what this host exists to exercise.
# ============================================================================================

INSTALLED_APPS += ["dynamic_user"]

MIDDLEWARE += []  # none required

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "dynamic_user_me": "60/min",
    "dynamic_user_profile_update": "20/min",
    "dynamic_user_setting_update": "20/min",
    "dynamic_user_profiles_list": "60/min",
    "dynamic_user_profile_retrieve": "60/min",
    "dynamic_user_deletion_request": "10/min",
    "dynamic_user_admin_users_list": "60/min",
    "dynamic_user_admin_user_retrieve": "60/min",
    "dynamic_user_admin_user_update": "30/min",
    "dynamic_user_admin_profile_update": "30/min",
    "dynamic_user_admin_setting_update": "30/min",
    "dynamic_user_admin_deletions_list": "60/min",
    "dynamic_user_admin_deletion_review": "20/min",
    "dynamic_user_admin_deletion_finalize": "10/min",
})

# The three top-level swappable settings point at `core`'s own subclasses — see core/models.py.
AUTH_USER_MODEL = "core.User"
DYNAMIC_USER_PROFILE_MODEL = "core.Profile"
DYNAMIC_USER_SETTING_MODEL = "core.Setting"

DYNAMIC_USER = {
    # `department` is core.User's own extra field — included here so it round-trips through
    # GET /me/ and the admin user read views without a serializer change.
    "USER_READ_FIELDS": [
        "id",
        "username",
        "name",
        "email",
        "phone",
        "is_active",
        "date_joined",
        "department",
    ],
    # `tagline` is core.Profile's own extra field — the field this playground's headline check
    # (Phase 8's "Verify") round-trips through a real PATCH with zero dynamic_user code changes.
    "PROFILE_EDITABLE_FIELDS": ["bio", "is_public", "tagline"],
    # `theme` is core.Setting's own extra field.
    "SETTING_EDITABLE_FIELDS": ["language", "timezone", "notifications_enabled", "theme"],
    # Tightened from the default host's False — the live comparison Phase 8 asks for: the same
    # "staff" login gets admin access on :8000 and 403 on :8001.
    "ADMIN_REQUIRES_SUPERUSER": True,
    # The default host proves hard_delete (the shipped default); this host proves the other
    # documented mode, backed by a real host-supplied anonymize callable.
    "DELETION_MODE": "anonymize",
    "DELETION_ANONYMIZE_FUNCTION": "core.anonymize.anonymize_user",
}

# ============================================================================================
# END DYNAMIC_USER WIRING
# ============================================================================================

from config.logging import build_logging_config  # noqa: E402

LOGGING = build_logging_config(debug=DEBUG)
