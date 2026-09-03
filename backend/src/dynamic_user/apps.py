"""This app's ``AppConfig`` — registers ``dynamic_user.checks``' system checks and, if enabled
(the default), connects the Profile/Setting auto-provisioning receivers from ``signals.py``.

Both actions happen from :meth:`DynamicUserConfig.ready`, never at module import time — a fresh,
unconfigured host must be able to import ``dynamic_user.apps`` (which Django does merely by
listing ``"dynamic_user"`` in ``INSTALLED_APPS``) without a settings lookup or a model resolution
ever running. Everything that touches settings or another module in this package is deferred
into ``ready()``, and every such import inside it is lazy — never at this module's top level —
so importing ``dynamic_user.apps`` alone can never trigger a settings access or an
``ImportError`` from a module that isn't ready yet.
"""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DynamicUserConfig(AppConfig):
    name = "dynamic_user"
    verbose_name = _("Dynamic User")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Register this app's system checks, then connect auto-provisioning receivers per the
        ``AUTO_CREATE_PROFILE``/``AUTO_CREATE_SETTING`` settings (both default ``True``).

        Registration/connection order is deliberate: checks are registered unconditionally and
        first, since they are what surfaces a misconfiguration in the first place; the
        auto-provisioning receivers are wired second and only under their own guard, since a
        host that has disabled one or both should see zero side effects from this app beyond
        the check itself.
        """
        from django.core.checks import register

        from dynamic_user import checks, conf, signals

        register(checks.check_swappable_model_settings)
        register(checks.check_deletion_settings)
        register(checks.check_field_allowlists)

        if conf.get_setting("AUTO_CREATE_PROFILE"):
            signals.connect_profile_auto_provisioning()

        if conf.get_setting("AUTO_CREATE_SETTING"):
            signals.connect_setting_auto_provisioning()
