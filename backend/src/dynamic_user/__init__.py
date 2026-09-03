"""``dynamic_user`` — the importable module for the ``django-dynamic-user`` distribution.

A standalone, versioned ``User``/``Profile``/``Setting`` data layer for a host Django project:
swappable models (installed as-is, or subclassed by a host for project-specific fields),
self-service and admin DRF surfaces, a Jazzmin admin, an opt-out account-deletion review flow, a
small mixin library, and frontend hooks for both surfaces. Depends on ``appkit`` (a real, versioned
dependency) for caching, pagination, permissions, the error envelope, and ``HttpClient``/provider.

**This app does not do authentication.** No registration, login, JWT, or password reset — that is
a separate ``auth-app`` package's job, reaching this one only through ``get_user_model()``, the
same indirection ``django.contrib.auth``'s own views use.

The PyPI distribution is ``django-dynamic-user``; npm is ``@hjtdev/django-dynamic-user``; the
GitHub repo is ``HjtDev/django-dynamic-user``. Only the local directory and this importable module
are ``dynamic_user``.

This module intentionally re-exports nothing. Each submodule below is its own public surface —
import from ``dynamic_user.<module>`` directly (e.g. ``from dynamic_user.resolution import
get_profile_model``), never from ``dynamic_user`` itself. Every model reference elsewhere in this
package is indirect: ``settings.AUTH_USER_MODEL`` for the user, ``dynamic_user.resolution`` for
the other two — never a concrete ``from dynamic_user.models import User/Profile/Setting`` import,
including from this package's own ``admin.py`` and ``services.py``. That indirection is the entire
point of this app: it is what lets a host subclass any of the three models.
"""
