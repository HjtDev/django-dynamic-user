"""This app's own emitted events, plus the two auto-provisioning receiver hooks ``apps.py``
wires from ``AppConfig.ready()``.

Every payload is a bare ID or primitive — never a model instance — so a host's own receiver
never needs this app's models imported just to read an event (``APP-DESIGN.md`` §6's minimality
rule). ``sender`` for ``profile_created``/``setting_created``/``profile_updated`` is the
*resolved* class (``resolution.get_profile_model()``/``get_setting_model()``, evaluated at
signal-send time, not import time) so a host can filter with
``@receiver(profile_created, sender=get_profile_model())`` even against a swapped model.
``AccountDeletionRequest`` is not swappable, so naming it concretely as ``sender`` for the three
deletion signals is safe.

Per ``docs/CONTRACT.md`` §3's minimality argument, per field:

* ``profile_created``/``setting_created`` carry only ``user_id`` — everything else about the new
  row is one query away, and neither name is stable enough across a host's subclass to belong in
  a fixed payload.
* ``deletion_requested`` carries ``request_id`` (so a receiver can act without a query) and
  ``finalize_at`` (the one piece of information time-sensitive enough to be worth avoiding a
  round-trip for). ``reason`` is omitted: free text, exactly what a fixed payload shouldn't
  couple to.
* ``deletion_reviewed`` carries ``status`` and ``reviewed_by_id`` — enough to compose "your
  request was approved/rejected by X" without a query.
* ``deletion_finalized`` carries ``mode`` (a receiver's correct behavior genuinely differs by
  it) and ``user_id`` (captured before a hard_delete removes the row, since after that there is
  no row left to query it from).
* ``profile_updated`` carries ``changed_fields``, not old/new values — enough for a receiver to
  decide *whether* it cares, without this package needing to serialize arbitrary before/after
  values of fields it doesn't control the shape of.

Requires another app package: No.

:func:`connect_profile_auto_provisioning` and :func:`connect_setting_auto_provisioning` each
connect a ``post_save`` receiver, keyed to the lazy string sender ``settings.AUTH_USER_MODEL``
(resolved by Django's own ``ModelSignal`` machinery, not this package, so it works unmodified
under a swapped ``AUTH_USER_MODEL``). ``apps.py``'s ``ready()`` calls each of these, independently,
under the matching ``AUTO_CREATE_PROFILE``/``AUTO_CREATE_SETTING`` boot-time guard; the receiver
body re-reads the same setting at call time before doing anything, so
``override_settings(DYNAMIC_USER={"AUTO_CREATE_PROFILE": False})`` disables provisioning inside a
test even though the receiver stays connected for the rest of the process
(``docs/CONTRACT.md`` §3, ``CLAUDE.md`` rule 2). On ``created=True``, each receiver calls
``get_or_create(user=instance)`` on the resolved Profile/Setting model and sends the matching
``*_created`` signal only when a row was actually created.
"""

from __future__ import annotations

from typing import Any, cast

import django.dispatch
from django.conf import settings
from django.db.models import Model
from django.db.models.signals import post_save

from dynamic_user import conf, resolution

profile_created = django.dispatch.Signal()
"""Sent after Profile auto-provisioning creates a row. sender=get_profile_model().
Payload: user_id: int"""

setting_created = django.dispatch.Signal()
"""Sent after Setting auto-provisioning creates a row. sender=get_setting_model().
Payload: user_id: int"""

deletion_requested = django.dispatch.Signal()
"""Sent by DeletionService.request(). sender=AccountDeletionRequest.
Payload: user_id: int, request_id: int, finalize_at: datetime"""

deletion_reviewed = django.dispatch.Signal()
"""Sent by DeletionService.review(). sender=AccountDeletionRequest.
Payload: request_id: int, status: str, reviewed_by_id: int | None"""

deletion_finalized = django.dispatch.Signal()
"""Sent by DeletionService.finalize(), AFTER the row/user mutation, but with user_id captured
BEFORE a hard_delete removes the row. sender=AccountDeletionRequest.
Payload: user_id: int, mode: str"""

profile_updated = django.dispatch.Signal()
"""Sent by ProfileService.update() when at least one field actually changed.
sender=get_profile_model(). Payload: user_id: int, changed_fields: list[str]"""


def _provision_profile(sender: type[Model], instance: Any, created: bool, **kwargs: Any) -> None:
    """The connected receiver body. Re-reads ``AUTO_CREATE_PROFILE`` at call time (not just at
    the boot-time gate ``apps.py`` already applies before connecting) so
    ``override_settings(DYNAMIC_USER={"AUTO_CREATE_PROFILE": False})`` actually disables
    provisioning inside a test — settings are resolved at call time everywhere in this package,
    never baked into a decision made once at import/``ready()`` time (``CLAUDE.md`` rule 2)."""
    if not created:
        return

    if not conf.get_setting("AUTO_CREATE_PROFILE"):
        return

    model = resolution.get_profile_model()
    # resolution.py types this as the bare `type[Model]`, which django-stubs gives no
    # `.objects` — see the equivalent cast in services.py.
    _, was_created = cast(Any, model).objects.get_or_create(user=instance)
    if was_created:
        profile_created.send(sender=model, user_id=instance.pk)


def _provision_setting(sender: type[Model], instance: Any, created: bool, **kwargs: Any) -> None:
    """Same shape as :func:`_provision_profile`, for Setting/``AUTO_CREATE_SETTING``/
    ``setting_created``."""
    if not created:
        return

    if not conf.get_setting("AUTO_CREATE_SETTING"):
        return

    model = resolution.get_setting_model()
    _, was_created = cast(Any, model).objects.get_or_create(user=instance)
    if was_created:
        setting_created.send(sender=model, user_id=instance.pk)


def connect_profile_auto_provisioning() -> None:
    """Connect the ``post_save(created=True)`` receiver that auto-creates a Profile row for a
    newly created user and sends ``profile_created``.

    Called from ``apps.py``'s ``ready()`` only when ``conf.get_setting("AUTO_CREATE_PROFILE")``
    is true (the default) — that call-time gate decides whether this function runs at all, not
    whether the connected receiver later provisions anything (:func:`_provision_profile`
    re-checks the same setting per-save). ``sender`` is the lazy string
    ``settings.AUTH_USER_MODEL`` — Django's ``ModelSignal.connect`` resolves an
    ``"app_label.ModelName"`` sender via ``apps.lazy_model_operation``, the same indirection
    ``get_user_model()`` itself relies on, so this connects correctly under a swapped
    ``AUTH_USER_MODEL`` with no concrete import here. ``dispatch_uid`` makes a second ``ready()``
    call (e.g. two app registries in one process, as some test runners do) a no-op reconnect
    rather than a duplicate receiver.
    """
    post_save.connect(
        _provision_profile,
        sender=settings.AUTH_USER_MODEL,
        dispatch_uid="dynamic_user.provision_profile",
    )


def connect_setting_auto_provisioning() -> None:
    """Connect the ``post_save(created=True)`` receiver that auto-creates a Setting row for a
    newly created user and sends ``setting_created``.

    Called from ``apps.py``'s ``ready()`` only when ``conf.get_setting("AUTO_CREATE_SETTING")``
    is true (the default). Same shape as :func:`connect_profile_auto_provisioning`, for Setting.
    """
    post_save.connect(
        _provision_setting,
        sender=settings.AUTH_USER_MODEL,
        dispatch_uid="dynamic_user.provision_setting",
    )
