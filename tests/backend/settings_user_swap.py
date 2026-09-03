"""The mirror image of ``settings_partial_swap.py``: ``AUTH_USER_MODEL`` is swapped to a
different app (``tests.backend.user_swap_app.User``) while ``DYNAMIC_USER_PROFILE_MODEL``/
``DYNAMIC_USER_SETTING_MODEL`` stay unset (default to ``dynamic_user``'s own ``Profile``/
``Setting``).

This is the settings module that actually needs
``migrations.swappable_dependency(settings.AUTH_USER_MODEL)`` present in ``dynamic_user``'s own
``0001_initial.py`` — without it, nothing in the migration graph guarantees
``user_swap_app``'s migration (creating its ``User`` table) runs before ``dynamic_user``'s own
migration creates ``Profile``/``Setting``/``AccountDeletionRequest``/``ChangeLogEntry``, all of
which FK/O2O to ``settings.AUTH_USER_MODEL``. See that migration file's own comment and
``docs/CONTRACT.md`` §10 item 14 for the full reasoning.
"""

from __future__ import annotations

from tests.backend.settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "tests.backend.user_swap_app"]  # noqa: F405

AUTH_USER_MODEL = "user_swap_app.User"
