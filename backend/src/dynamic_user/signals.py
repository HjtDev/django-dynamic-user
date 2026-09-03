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

Phase 3 implements the receiver bodies of :func:`connect_profile_auto_provisioning` and
:func:`connect_setting_auto_provisioning` (``dynamic_user.resolution`` — ``get_or_create`` on the
resolved Profile/Setting model, then send the matching ``*_created`` signal) exactly as
``docs/CONTRACT.md`` §3 specifies. ``apps.py``'s ``ready()`` already calls each of these,
independently, under the matching ``AUTO_CREATE_PROFILE``/``AUTO_CREATE_SETTING`` guard; what
they do today is connect nothing, since Phase 1 ships no model to receive ``post_save`` on the
user model in the first place.
"""

from __future__ import annotations

import django.dispatch

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


def connect_profile_auto_provisioning() -> None:
    """Connect the ``post_save(created=True)`` receiver that auto-creates a Profile row for a
    newly created user and sends ``profile_created``.

    Called from ``apps.py``'s ``ready()`` only when ``conf.get_setting("AUTO_CREATE_PROFILE")``
    is true (the default). Phase 3 implements the receiver body
    (``resolution.get_profile_model().objects.get_or_create(user=instance)`` then
    ``profile_created.send(...)``); this function is a real, importable, connectable no-op until
    then — never a bare ``pass`` placeholder module, since ``apps.py`` genuinely needs something
    to call.
    """


def connect_setting_auto_provisioning() -> None:
    """Connect the ``post_save(created=True)`` receiver that auto-creates a Setting row for a
    newly created user and sends ``setting_created``.

    Called from ``apps.py``'s ``ready()`` only when ``conf.get_setting("AUTO_CREATE_SETTING")``
    is true (the default). Same shape as :func:`connect_profile_auto_provisioning`, for Setting.
    """
