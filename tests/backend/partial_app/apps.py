"""A tiny host-style app subclassing only ``AbstractProfile``/``AbstractSetting`` — ``User``
stays ``dynamic_user.User`` (the default). Proves the decision recorded in this phase's plan: a
host swapping only Profile/Setting while leaving the user model at its default must not hit a
migration-graph cycle, which it would if ``dynamic_user/migrations/0001_initial.py`` carried
``migrations.swappable_dependency()`` for its own ``DYNAMIC_USER_PROFILE_MODEL``/
``DYNAMIC_USER_SETTING_MODEL`` settings (see ``docs/CONTRACT.md`` §10 item 14).

Exercised by ``tests/backend/settings_partial_swap.py``.
"""

from __future__ import annotations

from django.apps import AppConfig


class PartialAppConfig(AppConfig):
    name = "tests.backend.partial_app"
    label = "partial_app"
    default_auto_field = "django.db.models.BigAutoField"
