"""The host's own app, per docs/INTEGRATION-GUIDE.md §4's convention — the sanctioned place for a
host to import an app package directly (``core/models.py`` imports
``dynamic_user.models.AbstractDynamicUser``/``AbstractProfile``/``AbstractSetting``, the one
exception to "app packages never import each other, and nothing outside core/ imports one
either").
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    default_auto_field = "django.db.models.BigAutoField"
