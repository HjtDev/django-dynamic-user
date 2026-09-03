"""The partial-swap leg — ``AUTH_USER_MODEL`` stays at its default (``dynamic_user.User``) while
``DYNAMIC_USER_PROFILE_MODEL``/``DYNAMIC_USER_SETTING_MODEL`` point at
``tests.backend.partial_app``'s subclasses.

This is the settings module that proves ``docs/CONTRACT.md`` §10 item 14's decision: swapping
only Profile/Setting while leaving User at its default must not raise
``CircularDependencyError`` at migration time. It would, if ``dynamic_user/migrations/
0001_initial.py`` carried ``migrations.swappable_dependency()`` for its own
``DYNAMIC_USER_PROFILE_MODEL``/``DYNAMIC_USER_SETTING_MODEL`` settings — see that decision's full
reasoning in this phase's plan and in ``CONTRACT.md`` §10 item 14 itself.

Everything else is inherited from :mod:`tests.backend.settings` unchanged.
"""

from __future__ import annotations

from tests.backend.settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "tests.backend.partial_app"]  # noqa: F405

DYNAMIC_USER_PROFILE_MODEL = "partial_app.Profile"
DYNAMIC_USER_SETTING_MODEL = "partial_app.Setting"
