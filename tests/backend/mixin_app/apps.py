"""A tiny app whose sole model composes every mixin in ``dynamic_user.mixins`` — none of this
package's own default models use any of them (they're opt-in), so exercising them for real needs
somewhere to compose them into a concrete, migrated model. Installed in every settings module
(default, swapped, partial-swap alike) since the mixins are independent of which of the three
swappable models a host has swapped."""

from __future__ import annotations

from django.apps import AppConfig


class MixinAppConfig(AppConfig):
    name = "tests.backend.mixin_app"
    label = "mixin_app"
    default_auto_field = "django.db.models.BigAutoField"
