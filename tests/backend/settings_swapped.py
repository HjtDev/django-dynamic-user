"""The fully-swapped leg — ``AUTH_USER_MODEL``, ``DYNAMIC_USER_PROFILE_MODEL``, and
``DYNAMIC_USER_SETTING_MODEL`` all point at ``tests.backend.swapped_app``'s subclasses, proving
the swap machinery this app's entire design exists for actually works.

Everything else is inherited from :mod:`tests.backend.settings` unchanged — this file's only job
is to change which models the three swappable settings resolve to.
"""

from __future__ import annotations

from tests.backend.settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "tests.backend.swapped_app"]  # noqa: F405

AUTH_USER_MODEL = "swapped_app.User"
DYNAMIC_USER_PROFILE_MODEL = "swapped_app.Profile"
DYNAMIC_USER_SETTING_MODEL = "swapped_app.Setting"
