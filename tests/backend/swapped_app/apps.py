"""A tiny host-style app subclassing all three of this package's swappable abstract bases, each
with one extra field — proves the swap machinery works from Phase 2 onward, exercised by
``tests/backend/settings_swapped.py`` (all three swapped into this one app)."""

from __future__ import annotations

from django.apps import AppConfig


class SwappedAppConfig(AppConfig):
    name = "tests.backend.swapped_app"
    label = "swapped_app"
    default_auto_field = "django.db.models.BigAutoField"
