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
* ``dynamic_user.E003`` — ``DYNAMIC_USER["DELETION_MODE"]`` is not ``"hard_delete"`` or
  ``"anonymize"``, or it is ``"anonymize"`` while ``DYNAMIC_USER["DELETION_ANONYMIZE_FUNCTION"]``
  is unset. The contract's "fails closed, never silently falls back to hard-delete" promise
  (``docs/CONTRACT.md`` §6) caught at ``manage.py check`` time; ``services.DeletionService
  .finalize()`` raises the same ``ImproperlyConfigured`` at call time as the backstop for a
  command that skipped system checks.
* ``dynamic_user.E004`` — reserved for Phase 2: the resolved model does not subclass this app's
  own ``AbstractProfile``/``AbstractSetting``. Cannot be implemented until those abstract bases
  exist (``docs/CONTRACT.md`` §1, built in Phase 2) — ``models.py`` ships empty in Phase 1 by
  design (this phase's own build prompt, item 8).
* ``dynamic_user.E005`` — a name in a ``*_FIELDS`` allowlist that doesn't exist on the resolved
  model it's checked against (``docs/CONTRACT.md`` §6). One of two cooperating mechanisms: this
  check catches it at ``manage.py check``/startup time; ``serializers.build_serializer()`` (via
  every accessor in ``serializers.py``) raises the same-shaped ``ImproperlyConfigured`` at call
  time as the backstop for a command that skipped system checks. Both share
  ``serializers._unknown_field_message()`` so the message is identical either way.

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

from collections.abc import Callable, Sequence
from typing import Any

from django.apps import apps as django_apps
from django.apps.config import AppConfig
from django.core.checks import CheckMessage, Error

from dynamic_user import conf, resolution


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


def check_deletion_settings(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """``dynamic_user.E003`` — validate ``DYNAMIC_USER["DELETION_MODE"]`` and, when it's
    ``"anonymize"``, that ``DYNAMIC_USER["DELETION_ANONYMIZE_FUNCTION"]`` is actually set. Catches
    at ``manage.py check``/startup time the same misconfiguration
    ``services.DeletionService.finalize()`` would otherwise only discover mid-request, the first
    time a request is finalized in anonymize mode.
    """
    mode = conf.get_setting("DELETION_MODE")

    if mode not in ("hard_delete", "anonymize"):
        return [
            Error(
                f'DYNAMIC_USER["DELETION_MODE"] is "{mode}", which is neither "hard_delete" '
                'nor "anonymize".',
                id="dynamic_user.E003",
            )
        ]

    if mode == "anonymize" and not conf.get_setting("DELETION_ANONYMIZE_FUNCTION"):
        return [
            Error(
                'DYNAMIC_USER["DELETION_MODE"] is "anonymize" but '
                'DYNAMIC_USER["DELETION_ANONYMIZE_FUNCTION"] is not set.',
                id="dynamic_user.E003",
            )
        ]

    return []


def check_field_allowlists(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """``dynamic_user.E005`` — validate every ``DYNAMIC_USER`` ``*_FIELDS`` allowlist against the
    *resolved* model it configures a serializer for (``docs/CONTRACT.md`` §6's first of two
    cooperating mechanisms; the second is ``serializers.build_serializer()``'s own
    ``ImproperlyConfigured`` at call time).

    Imports ``serializers.py`` and ``django.contrib.auth.get_user_model()`` function-locally, not
    at this module's top level — ``apps.py``'s ``ready()`` must be able to register every check
    unconditionally before anything settings-dependent runs, and importing ``serializers.py``
    (which imports ``rest_framework``) at ``checks.py`` import time would make DRF a hard,
    eager import for every host that merely lists ``"dynamic_user"`` in ``INSTALLED_APPS``.

    Never raises: if a swappable-model setting is itself malformed (already reported by
    ``dynamic_user.E001``/``E002``), resolution is skipped for that model rather than letting the
    resulting exception propagate out of a system check.
    """
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ImproperlyConfigured
    from django.db.models import Model

    from dynamic_user.serializers import _unknown_field_message, _valid_field_names

    resolvers: list[tuple[Callable[[], type[Model]], list[str]]] = [
        (
            get_user_model,
            [
                "USER_READ_FIELDS",
                "USER_EDITABLE_FIELDS",
                "USER_LOCKED_FIELDS",
                "USER_PUBLIC_FIELDS",
            ],
        ),
        (
            resolution.get_profile_model,
            ["PROFILE_READ_FIELDS", "PROFILE_EDITABLE_FIELDS", "PROFILE_PUBLIC_FIELDS"],
        ),
        (
            resolution.get_setting_model,
            ["SETTING_READ_FIELDS", "SETTING_EDITABLE_FIELDS"],
        ),
    ]

    errors: list[CheckMessage] = []
    for get_model, setting_keys in resolvers:
        try:
            model = get_model()
        except ImproperlyConfigured:
            # dynamic_user.E001/E002 already report a malformed swappable-model setting for this
            # model — skip it here rather than letting resolution's own exception propagate out
            # of a system check, which must never raise.
            continue

        valid = _valid_field_names(model)
        for setting_key in setting_keys:
            for field in conf.get_setting(setting_key):
                if field not in valid:
                    errors.append(
                        Error(
                            _unknown_field_message(field, model, setting_key),
                            id="dynamic_user.E005",
                        )
                    )

    try:
        user_model = get_user_model()
    except ImproperlyConfigured:
        return errors

    valid_user_fields = _valid_field_names(user_model)
    for field in conf.get_privileged_fields():
        if field not in valid_user_fields:
            errors.append(
                Error(
                    _unknown_field_message(field, user_model, "USER_PRIVILEGED_FIELDS"),
                    id="dynamic_user.E005",
                )
            )

    return errors
