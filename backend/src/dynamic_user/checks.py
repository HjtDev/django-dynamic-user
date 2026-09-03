"""Django system checks for this app's two swappable-model settings.

Registered explicitly from ``apps.py``'s ``ready()`` — via ``django.core.checks.register()``,
never Django's checks-app-config auto-discovery convention — so a fresh, unconfigured host never
sees an ``ImportError`` while collecting ``apps.py`` itself; a missing/malformed setting is a
check *error* at ``manage.py check``/startup time, and nothing else. Mirrors
``django.contrib.auth``'s own ``AUTH_USER_MODEL`` checks (``auth.E002``/``E003``) in both shape
and error-code style.

ID → function table:

* ``dynamic_user.E001`` — ``DYNAMIC_USER_PROFILE_MODEL``/``DYNAMIC_USER_SETTING_MODEL`` is not
  of the form ``'app_label.ModelName'``.
* ``dynamic_user.E002`` — the setting refers to a model that has not been installed.
* ``dynamic_user.E003`` — reserved, unused as of Phase 1.
* ``dynamic_user.E004`` — reserved for Phase 2: the resolved model does not subclass this app's
  own ``AbstractProfile``/``AbstractSetting``. Cannot be implemented until those abstract bases
  exist (``docs/CONTRACT.md`` §1, built in Phase 2) — ``models.py`` ships empty in Phase 1 by
  design (this phase's own build prompt, item 8).
* ``dynamic_user.E005`` — reserved for Phase 4: a name in a ``*_FIELDS`` allowlist that doesn't
  exist on the resolved model (``docs/CONTRACT.md`` §6).

Every check function returns a list of ``django.core.checks.Error`` — none of them ever raises.
A system check that raises breaks ``manage.py`` entirely, for every command, not just ``check``;
treating malformed host config as a returned ``Error``, never an exception, is what keeps
``manage.py migrate``/``runserver``/etc. usable enough to fix the misconfiguration in the first
place (the same rule ``appkit.checks`` documents for its own checks).

**Unset-setting behavior in Phase 1, explained** (reconciles two statements that look
contradictory at first read): ``docs/CONTRACT.md`` §6 says ``DYNAMIC_USER_PROFILE_MODEL``/
``_SETTING_MODEL`` *default* to ``"dynamic_user.Profile"``/``"dynamic_user.Setting"`` when unset
— a host is expected to override them, but omitting them is not itself an error. In Phase 1,
``models.py`` is still empty, so that default resolves to a model that genuinely does not exist
yet: ``apps.get_model()`` raises ``LookupError``, and ``dynamic_user.E002`` fires with "...
refers to model ... that has not been installed" — exactly the check-error, no-traceback
behavior this phase's own verification step requires. From Phase 2 onward, once Profile/Setting
are real, that same default resolves cleanly and an unset setting stops being an error at all.
This is not a bug to fix in Phase 2 — it is Phase 1's empty ``models.py`` making the contract's
own default do the right thing by construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.apps import apps as django_apps
from django.apps.config import AppConfig
from django.core.checks import CheckMessage, Error

from dynamic_user import resolution


def check_swappable_model_settings(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """``dynamic_user.E001``/``dynamic_user.E002`` — validate the shape and installed-ness of
    ``DYNAMIC_USER_PROFILE_MODEL`` and ``DYNAMIC_USER_SETTING_MODEL``.

    Registered from ``apps.py``'s ``ready()`` via ``django.core.checks.register()``, not
    auto-discovered — mirrors ``appkit.checks``'s own explicit-registration pattern.
    """
    errors: list[CheckMessage] = []
    errors.extend(
        _check_model_setting("DYNAMIC_USER_PROFILE_MODEL", resolution.get_profile_model_string())
    )
    errors.extend(
        _check_model_setting("DYNAMIC_USER_SETTING_MODEL", resolution.get_setting_model_string())
    )
    return errors


def _check_model_setting(setting_name: str, value: str) -> list[CheckMessage]:
    """Shared implementation behind :func:`check_swappable_model_settings` — not part of this
    module's public surface."""
    if not isinstance(value, str) or value.count(".") != 1:
        return [
            Error(
                f"{setting_name} must be of the form 'app_label.ModelName'.",
                id="dynamic_user.E001",
            )
        ]

    try:
        django_apps.get_model(value, require_ready=False)
    except LookupError:
        return [
            Error(
                f"{setting_name} refers to model '{value}' that has not been installed.",
                id="dynamic_user.E002",
            )
        ]

    return []
