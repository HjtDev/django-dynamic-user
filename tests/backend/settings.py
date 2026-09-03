"""Minimal Django settings for this app's own test suite — the DEFAULT-models leg.

Lives in the test tree, not the package — the package must never contain a settings file
(``APP-DESIGN.md`` §7.1). Kept deliberately minimal: if this app's tests only pass with extra
apps installed, it has an undeclared dependency on host configuration.

**``appkit`` is now in ``INSTALLED_APPS``**, added in Phase 5 — the views layer is where it
becomes a real, load-bearing dependency (``permissions.IsObjectOwner``, ``mixins.CachedListMixin``,
``pagination.DefaultPagination``, ``exceptions.standard_exception_handler``,
``request_id.RequestIDMiddleware``), per this file's own previous-phase note. Installing it engages
``appkit.checks.check_request_id_middleware``/``check_exception_handler``
(``appkit.E001``/``E002``, both check Errors) and ``check_throttle_scopes``
(``appkit.W004``) — satisfied below by the middleware entry, ``EXCEPTION_HANDLER``, and
``DEFAULT_THROTTLE_RATES`` respectively, mirroring ``cleanup_app``'s own
``tests/backend/settings.py``, the sibling app package that wired the same dependency first.

``django.contrib.admin`` (+ ``sessions``/``messages``/``staticfiles``, its own dependencies) IS
listed — this app ships ``admin.py`` registrations that this phase's own tests exercise through a
real Django admin changelist and actions.

No ``DYNAMIC_USER`` dict at all — every key in it is optional with a documented default
(``dynamic_user/conf.py``), and omitting it entirely is what proves that. Individual tests use
``override_settings`` where a non-default value matters.

No ``DEFAULT_AUTHENTICATION_CLASSES`` override — DRF's own defaults
(``SessionAuthentication`` first, ``BasicAuthentication`` second) are what a bare host gets, and
neither ``base-scaffold``'s nor ``cleanup_app``'s own test settings override this either. An
anonymous request therefore surfaces as ``403``, not ``401``:
``APIView.handle_exception`` only keeps a ``NotAuthenticated`` at 401 when
``get_authenticate_header()`` returns a non-empty ``WWW-Authenticate`` value, and
``SessionAuthentication`` (checked first) deliberately returns none. The ``error.code`` stays
``"not_authenticated"`` regardless — that's what actually distinguishes this case from
authenticated-but-forbidden, not the HTTP status (see ``test_views.py``).
"""

from __future__ import annotations

import os

SECRET_KEY = "test-only-not-a-secret"
DEBUG = False
USE_TZ = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "rest_framework",
    "drf_spectacular",
    "appkit",
    "dynamic_user",
    "tests.backend.mixin_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "appkit.request_id.RequestIDMiddleware",  # right after SecurityMiddleware — appkit.W002
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

ROOT_URLCONF = "tests.backend.urls"

STATIC_URL = "/static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Every value below is overridable by an env var — the literal defaults are what a bare
# `uv run pytest` needs against a Postgres already listening on localhost:5432 with the
# postgres/postgres superuser; this repo's Makefile/docker-compose.test.yml export
# POSTGRES_HOST/POSTGRES_PORT=55434 to point at the ephemeral container instead
# (``docs/APP-DESIGN.md`` §7.5).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "test_dynamic_user"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Every DRF-raised error (validation, 401/403/404/405/409/429, unhandled 500) renders in
    # appkit's one documented envelope shape — satisfies appkit.E002.
    "EXCEPTION_HANDLER": "appkit.exceptions.standard_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "appkit.pagination.DefaultPagination",
    # Without this, a view's declared `throttle_scope` is inert — nothing actually enforces it.
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    # The six Phase 5 self-service scopes, literal strings per docs/CONTRACT.md §5 (never
    # appkit.throttling.throttle_scope() — that helper rejects any argument containing "_", and
    # "dynamic_user" has one). appkit.checks.check_throttle_scopes (W004) validates each view's
    # declared throttle_scope against this dict.
    "DEFAULT_THROTTLE_RATES": {
        "dynamic_user_me": "60/min",
        "dynamic_user_profile_update": "20/min",
        "dynamic_user_setting_update": "20/min",
        "dynamic_user_profiles_list": "60/min",
        "dynamic_user_profile_retrieve": "60/min",
        "dynamic_user_deletion_request": "10/min",
    },
    # appkit.W006: with a rate-limiting throttle class configured (above) and NUM_PROXIES unset,
    # SimpleRateThrottle.get_ident() joins X-Forwarded-For's full chain into the cache key, so a
    # spoofed header could mint a fresh bucket per request. Matches APPKIT["TRUSTED_PROXY_COUNT"]'s
    # own default of 1 (no APPKIT dict here, so that default applies).
    "NUM_PROXIES": 1,
}

# COMPONENT_SPLIT_REQUEST is required, not optional (APP-DESIGN.md §12, "Generated types") —
# wired now even though Phase 2 generates no schema yet, so a later phase's schema generation
# needs no further settings changes.
SPECTACULAR_SETTINGS = {
    "TITLE": "django-dynamic-user",
    "VERSION": "0.0.0",  # irrelevant here — the app's real version lives in pyproject.toml
    "COMPONENT_SPLIT_REQUEST": True,
}

AUTH_USER_MODEL = "dynamic_user.User"
DYNAMIC_USER_PROFILE_MODEL = "dynamic_user.Profile"
DYNAMIC_USER_SETTING_MODEL = "dynamic_user.Setting"
