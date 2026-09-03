"""The fully-swapped leg — ``AUTH_USER_MODEL``, ``DYNAMIC_USER_PROFILE_MODEL``, and
``DYNAMIC_USER_SETTING_MODEL`` all point at ``tests.backend.swapped_app``'s subclasses, proving
the swap machinery this app's entire design exists for actually works.

Everything else is inherited from :mod:`tests.backend.settings` unchanged — this file's only job
is to change which models the three swappable settings resolve to.

Phase 4 adds a ``DYNAMIC_USER`` dict here (the base settings module deliberately carries none, to
prove every key is optional) naming ``swapped_app``'s own extra fields —
``User.department``/``Profile.tagline``/``Setting.theme`` — in the allowlists a serializer
factory test round-trips through, proving the factory reaches the resolved subclass's real
fields rather than a hardcoded default.
"""

from __future__ import annotations

from tests.backend.settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "tests.backend.swapped_app"]  # noqa: F405

AUTH_USER_MODEL = "swapped_app.User"
DYNAMIC_USER_PROFILE_MODEL = "swapped_app.Profile"
DYNAMIC_USER_SETTING_MODEL = "swapped_app.Setting"

DYNAMIC_USER = {
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
    "PROFILE_EDITABLE_FIELDS": ["bio", "is_public", "tagline"],
    "SETTING_EDITABLE_FIELDS": ["language", "timezone", "notifications_enabled", "theme"],
}
