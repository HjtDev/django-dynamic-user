"""Default-host playground settings — Phase 8, docs/APP-DESIGN.md §11.2.

Split into two halves, mirroring ../../../cleanup_app/playground/backend/config/settings.py's own
convention (app package #2's Phase 7 playground):

  1. "HOST BASELINE" — what a fresh Django host already has before any app package is installed.
  2. "DYNAMIC_USER WIRING" — the block a host's own README-copied config would contain. There is
     no root README.md yet (that's Phase 9, written AFTER this playground and validated against
     it) — this block is instead derived directly from docs/CONTRACT.md §5/§6, and is written to
     BECOME Phase 9's README config fence once one exists.

Installs dynamic_user with ZERO customization — AUTH_USER_MODEL = "dynamic_user.User", the
package's own concrete Profile/Setting, no DYNAMIC_USER dict at all. Omitting DYNAMIC_USER
entirely (same convention as tests/backend/settings.py) is deliberate: every one of its 20 keys is
optional with a documented default (dynamic_user/conf.py), and this is what proves it live, not
just in a unit test.

No reverse proxy sits between the browser and this backend at the HTTP layer: the Next.js app's
`rewrites()` (default/frontend/next.config.ts) proxy same-origin requests server-side, which does
not forward X-Forwarded-For — so NUM_PROXIES/TRUSTED_PROXY_COUNT stay at 0, not 1, mirroring
cleanup_app's own playground for the same reason.
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
    "ALLOWED_HOSTS", default="localhost,127.0.0.1,backend-default", cast=lambda v: v.split(",")
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
    # appkit is a prerequisite of dynamic_user, not part of its own wiring block below — a real
    # host installs and wires appkit FIRST (per appkit's own README), then adds dynamic_user on
    # top. Omitting this leaves REST_FRAMEWORK on DRF's stock exception handler, so
    # IsDynamicUserAdmin's 403 comes back as DRF's bare {"detail": ...} shape instead of appkit's
    # error envelope — the exact failure mode cleanup_app's own playground found live (see its
    # FINDINGS.md #3).
    "appkit",
    "demo",
    # ---- DYNAMIC_USER WIRING adds "dynamic_user" below ----
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "appkit.request_id.RequestIDMiddleware",  # right after SecurityMiddleware, per appkit's README
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
        "NAME": config("POSTGRES_DB", default="playground_default"),
        "USER": config("POSTGRES_USER", default="playground"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="playground"),
        "HOST": config("POSTGRES_HOST", default="db"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

# A real cache backend, not locmem — PublicProfileListView's CachedListMixin snapshot needs one
# shared across the backend and celery worker processes to mean anything here.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://redis:6379/0"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

CELERY_BROKER_URL = config("REDIS_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://redis:6379/0")
CELERY_TASK_ALWAYS_EAGER = False

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

CSRF_COOKIE_HTTPONLY = False  # must stay JS-readable — the frontend sends it as a header
SESSION_COOKIE_HTTPONLY = True

# The Next.js dev server proxies same-origin (localhost:3000 -> backend-default:8000
# server-side), so the browser's own origin for CSRF purposes is localhost:3000, not this
# container.
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:3000",
    cast=lambda v: v.split(","),
)

# django.contrib.auth.urls's LoginView/LogoutView — no "?next=" means "go here" (the frontend's
# own home page, proxied same-origin).
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

REST_FRAMEWORK: dict[str, object] = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # appkit's own required wiring — every IsDynamicUserAdmin rejection and every
    # ValidationError dynamic_user raises renders through this, not DRF's stock {"detail": ...}
    # shape.
    "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "appkit.pagination.DefaultPagination",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    # No untrusted reverse proxy sits between the browser and this backend: the Next.js app's
    # server-side rewrites() do not forward X-Forwarded-For, so there are zero trusted hops to
    # skip — matches APPKIT["TRUSTED_PROXY_COUNT"] below (appkit.W006 fires on any disagreement).
    "NUM_PROXIES": 0,
    # Starts empty — dynamic_user's own 14 throttle_scope rates are added below, by the
    # DYNAMIC_USER WIRING block's own .update({...}) call, exactly as a host's README-copied
    # config would.
    "DEFAULT_THROTTLE_RATES": {},
}

APPKIT = {
    "TRUSTED_PROXY_COUNT": 0,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "django-dynamic-user playground — default host",
    "VERSION": "0.1.0",
    "COMPONENT_SPLIT_REQUEST": True,
}

JAZZMIN_SETTINGS = {
    "site_title": "dynamic_user playground",
    "site_header": "Playground (default)",
    "site_brand": "django-dynamic-user",
    "welcome_sign": "Dynamic User Playground — default models",
    # backend/src/dynamic_user/admin.py's own docstring suggests these — this is the live check
    # that the suggestion Phase 9's README ships is actually copy-pasteable.
    "icons": {
        "dynamic_user.user": "fas fa-user",
        "dynamic_user.profile": "fas fa-id-card",
        "dynamic_user.setting": "fas fa-sliders-h",
        "dynamic_user.accountdeletionrequest": "fas fa-user-slash",
        "dynamic_user.changelogentry": "fas fa-history",
    },
}

# ============================================================================================
# DYNAMIC_USER WIRING — derived from docs/CONTRACT.md §5 (throttle scopes) and §6 (settings).
# Written to become Phase 9's README config fence verbatim once one exists — do not reorder,
# merge, tune, or "improve" anything between these banners; playground-specific values live in
# the host-specific block below the END banner instead.
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

# The package's own concrete models, used as-is — this host's whole point. No DYNAMIC_USER dict
# at all: every key is optional with a documented default (dynamic_user/conf.py DEFAULTS), and
# this host proves that live rather than just asserting it in a unit test. In particular
# ADMIN_REQUIRES_SUPERUSER stays False (default — staff can admin) and DELETION_MODE stays
# "hard_delete" (default) here; the subclassed host flips both, so the two postures are
# comparable side by side without a restart.
AUTH_USER_MODEL = "dynamic_user.User"
DYNAMIC_USER_PROFILE_MODEL = "dynamic_user.Profile"
DYNAMIC_USER_SETTING_MODEL = "dynamic_user.Setting"

# ============================================================================================
# END DYNAMIC_USER WIRING
# ============================================================================================

from config.logging import build_logging_config  # noqa: E402

LOGGING = build_logging_config(debug=DEBUG)
