"""A host-style subclass of all three of ``dynamic_user``'s abstract bases, each with one extra
field — the artifact Phase 9's README lifts verbatim as its worked subclassing example. Mirrors
``tests/backend/swapped_app/models.py`` in the main repo exactly (the proven-working pattern this
whole package's design exists to support).

None of these three declare ``Meta.swappable`` themselves — that attribute belongs to
``dynamic_user``'s own default implementation (``dynamic_user.models.User``/``Profile``/
``Setting``), marking "this is the model a setting can swap away from". A host's replacement model
is simply whatever ``AUTH_USER_MODEL``/``DYNAMIC_USER_PROFILE_MODEL``/``DYNAMIC_USER_SETTING_MODEL``
(``config/settings.py``) name — it needs no ``swappable`` attribute of its own, exactly like any
other project's custom ``AUTH_USER_MODEL``.
"""

from __future__ import annotations

from django.db import models

from dynamic_user.managers import UserManager
from dynamic_user.models import AbstractDynamicUser, AbstractProfile, AbstractSetting


class User(AbstractDynamicUser):
    department = models.CharField(max_length=100, blank=True)

    # Required — AbstractDynamicUser doesn't declare `objects` as inheritable in a way Django's
    # migration state picks up automatically; every host subclass must re-declare it. Easy to
    # omit; `createsuperuser`/`create_user` breaks with a cryptic error without it.
    objects = UserManager()


class Profile(AbstractProfile):
    # The field this playground's headline check (Phase 8's "Verify") round-trips through a real
    # PATCH — DYNAMIC_USER["PROFILE_EDITABLE_FIELDS"] (config/settings.py) includes it, with zero
    # changes to dynamic_user's own serializers/views.
    tagline = models.CharField(max_length=200, blank=True)


class Setting(AbstractSetting):
    theme = models.CharField(max_length=20, default="light")
