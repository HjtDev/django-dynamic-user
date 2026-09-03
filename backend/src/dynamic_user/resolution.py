"""Resolves this app's two swappable models — Profile and Setting — the same way
``django.contrib.auth.get_user_model()`` resolves ``AUTH_USER_MODEL``.

Requires another app package: No.

:func:`get_profile_model`/:func:`get_setting_model` read ``DYNAMIC_USER_PROFILE_MODEL``/
``DYNAMIC_USER_SETTING_MODEL`` (falling back to this app's own documented defaults,
``conf.PROFILE_MODEL_DEFAULT``/``conf.SETTING_MODEL_DEFAULT``, per ``docs/CONTRACT.md`` §6),
resolve via ``django.apps.apps.get_model(..., require_ready=False)``, and raise
``django.core.exceptions.ImproperlyConfigured`` naming the exact misconfigured setting on
failure — never a bare ``AttributeError``/``LookupError``.

No local cache: ``django.apps.apps.get_model()`` is already cached and already invalidated by
the app registry's own lifecycle — Django clears that cache on every app-registry-affecting
event, including between test runs. A hand-rolled module-level dict on top of that would
duplicate a cache Django already maintains correctly, and — per ``docs/CONTRACT.md`` §2's
explicit warning — would NOT be invalidated the same way, so it would go stale across a test
suite's database teardown/rebuild between test modules. Mirrors
``django.contrib.auth.get_user_model()``, which takes exactly this same "no extra cache"
approach.
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model

from dynamic_user import conf


def get_profile_model_string() -> str:
    """Return the configured ``DYNAMIC_USER_PROFILE_MODEL`` string, or this app's documented
    default (``"dynamic_user.Profile"``) if unset."""
    value: str = getattr(settings, "DYNAMIC_USER_PROFILE_MODEL", conf.PROFILE_MODEL_DEFAULT)
    return value


def get_setting_model_string() -> str:
    """Return the configured ``DYNAMIC_USER_SETTING_MODEL`` string, or this app's documented
    default (``"dynamic_user.Setting"``) if unset."""
    value: str = getattr(settings, "DYNAMIC_USER_SETTING_MODEL", conf.SETTING_MODEL_DEFAULT)
    return value


def get_profile_model() -> type[Model]:
    """Resolve and return the configured Profile model class.

    Raises:
        ImproperlyConfigured: ``DYNAMIC_USER_PROFILE_MODEL`` is malformed or names a model that
            isn't installed — naming the exact setting in the message, mirroring
            ``django.contrib.auth.get_user_model()``'s own error shape.
    """
    return _resolve_model("DYNAMIC_USER_PROFILE_MODEL", get_profile_model_string())


def get_setting_model() -> type[Model]:
    """Resolve and return the configured Setting model class.

    Raises:
        ImproperlyConfigured: ``DYNAMIC_USER_SETTING_MODEL`` is malformed or names a model that
            isn't installed — naming the exact setting in the message.
    """
    return _resolve_model("DYNAMIC_USER_SETTING_MODEL", get_setting_model_string())


def _resolve_model(setting_name: str, model_string: str) -> type[Model]:
    """Shared implementation behind :func:`get_profile_model`/:func:`get_setting_model` — not
    part of this module's public surface."""
    try:
        return django_apps.get_model(model_string, require_ready=False)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"{setting_name} must be of the form 'app_label.ModelName'."
        ) from exc
    except LookupError as exc:
        raise ImproperlyConfigured(
            f"{setting_name} refers to model '{model_string}' that has not been installed."
        ) from exc
