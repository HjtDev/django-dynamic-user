"""A tiny host-style app subclassing ONLY ``AbstractDynamicUser`` — ``Profile``/``Setting`` stay
at ``dynamic_user``'s own defaults. The mirror image of ``partial_app`` (which swaps
Profile/Setting only): this is the scenario that actually needs
``migrations.swappable_dependency(settings.AUTH_USER_MODEL)`` present in ``dynamic_user``'s own
``0001_initial.py`` — see that file's own comment and ``docs/CONTRACT.md`` §10 item 14.

Exercised by ``tests/backend/settings_user_swap.py``.
"""

from __future__ import annotations

from django.apps import AppConfig


class UserSwapAppConfig(AppConfig):
    name = "tests.backend.user_swap_app"
    label = "user_swap_app"
    default_auto_field = "django.db.models.BigAutoField"
