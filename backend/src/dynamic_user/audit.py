"""v1.1.0. Makes an admin-API write auditable the same way a Django Admin write already is.

Every write made through Django Admin gets a ``django.contrib.admin.models.LogEntry`` row —
Django's own machinery writes one automatically from ``ModelAdmin.log_addition``/
``log_change``/``log_deletion``. Every write made through this app's admin **API**
(``admin_views.py``) wrote none at all before v1.1.0 — a real audit-trail gap the parity audit
that motivated this release surfaced. :func:`log_admin_action` closes it: one call per admin-API
write path, producing the identical row shape Django Admin itself would have produced for the
same change.

A no-op, always, when ``django.contrib.admin`` isn't installed — this app has no hard dependency
on it (``docs/CONTRACT.md`` §0), and an API-only host running without the admin app installed at
all must see zero behavior difference from calling this function. Guarded with
``django.apps.apps.is_installed`` rather than a bare ``try/except ImportError``, mirroring
``urls_admin.py``'s own guard for the same reason — the import itself would succeed either way
(``django.contrib.admin.models`` is just a Python module); what actually fails without the app
installed is writing to a table that was never migrated.
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import Model


def log_admin_action(
    *,
    actor: AbstractBaseUser | None,
    obj: Model,
    action_flag: int,
    message: str = "",
) -> None:
    """Write one ``LogEntry`` row for an admin-API write — additive, best-effort, and silent by
    design: an audit-log write must never be the reason a real request fails. ``action_flag`` is
    one of ``django.contrib.admin.models.ADDITION``/``CHANGE``/``DELETION``. ``actor`` is
    ``None``-safe (an unauthenticated caller can never reach an admin view in the first place, but
    this function makes no assumption about that) — a ``None``/anonymous actor logs with
    ``user_id=None`` rather than raising.
    """
    if not django_apps.is_installed("django.contrib.admin"):
        return

    from django.contrib.admin.models import LogEntry

    user_id = actor.pk if actor is not None and actor.is_authenticated else None
    if user_id is None:
        # LogEntry.user_id is NOT NULL — an action with no identifiable actor has nothing
        # meaningful to attribute it to, so it is skipped rather than logged against a fake user.
        return

    # LogEntryManager.log_action() (singular) was removed in Django 6.0 — log_actions() (plural,
    # queryset-based, added ahead of that removal) is the one shape available across this
    # package's whole declared range (django>=5.2,<7.0). single_object=True asks it to behave
    # like the old singular API for exactly this one-object case.
    LogEntry.objects.log_actions(
        user_id, [obj], action_flag, change_message=message, single_object=True
    )
