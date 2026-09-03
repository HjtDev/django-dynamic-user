"""Minimal Django settings for this app's own test suite — the DEFAULT-models leg.

Lives in the test tree, not the package — the package must never contain a settings file
(``APP-DESIGN.md`` §7.1). Kept deliberately minimal: if this app's tests only pass with extra
apps installed, it has an undeclared dependency on host configuration.

**``appkit`` is deliberately NOT in ``INSTALLED_APPS`` here.** Nothing built so far
(``models.py``, ``mixins.py``, ``validators.py``, the ``DeletionService.review`` slice of
``services.py``, ``admin.py``) imports or calls into ``appkit`` — it becomes a real, load-bearing
dependency starting with the views layer. Installing it now would also engage
``appkit.checks.check_request_id_middleware``/``check_exception_handler`` (``appkit.E001``/
``E002``), which `manage.py migrate`'s default system-check pass would then fail on for
configuration this phase has no reason to carry yet. Added when a phase's own tests need it.

``django.contrib.admin`` (+ ``sessions``/``messages``/``staticfiles``, its own dependencies) IS
listed — this app ships ``admin.py`` registrations that this phase's own tests exercise through a
real Django admin changelist and actions.

No ``DYNAMIC_USER`` dict at all — every key in it is optional with a documented default
(``dynamic_user/conf.py``), and omitting it entirely is what proves that. Individual tests use
``override_settings`` where a non-default value matters.
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
    "dynamic_user",
    "tests.backend.mixin_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
