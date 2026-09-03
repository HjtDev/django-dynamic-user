"""Region-specific validator hooks — the ``PHONE_VALIDATORS``/``NAME_VALIDATORS`` settings made
real.

:func:`run_validators` resolves the dotted callable paths configured under
``DYNAMIC_USER[setting_key]`` lazily and caches the *imported callables* on first use, calling
each in turn and raising ``django.core.exceptions.ValidationError`` on the first failure. Empty
(the default for both keys) means no extra validation beyond Django's own field checks — this
module ships no opinionated phone/name format of its own; the hook is the feature, not a
validator (this repo's scope-boundary table).

Caching strategy, spelled out because it is easy to get backwards: the *setting itself*
(``conf.get_setting(setting_key)``, a list of dotted paths) is read fresh on every call — never
cached — so a host changing ``DYNAMIC_USER[setting_key]`` (directly, or via ``override_settings``
in a test) takes effect on the very next call with no process restart. Only the *result of
importing* a given dotted path is cached, keyed by that path string, so a validator already
resolved once is never re-imported on a later call even if the setting still lists it. Import
happens no earlier than the first actual call to :func:`run_validators` — never at ``models.py``
or any other module's import time, per ``docs/APP-DESIGN.md``/this repo's ``CLAUDE.md`` rule 2.

Fails closed: a dotted path that can't be imported (``ImportError``, a bad module path, a name
that isn't callable) raises ``ValidationError`` naming the offending setting key and path, rather
than silently skipping that validator and accepting the input — per
``CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`` §0 item 3, "an unconfigured or unresolvable validator
path rejects input rather than silently accepting anything."
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.module_loading import import_string

from dynamic_user import conf

#: dotted path -> resolved callable. Populated lazily, only from inside run_validators() — never
#: at this module's import time.
_resolved_validators: dict[str, Callable[[Any], None]] = {}


def run_validators(setting_key: str, value: Any) -> None:
    """Run every validator configured under ``DYNAMIC_USER[setting_key]`` against ``value``, in
    order, stopping at the first failure.

    Args:
        setting_key: e.g. ``"PHONE_VALIDATORS"``/``"NAME_VALIDATORS"`` — any ``DYNAMIC_USER`` key
            whose value is a list of dotted callable paths.
        value: the value to validate.

    Raises:
        ValidationError: a configured validator rejected ``value``, or a configured dotted path
            could not be imported/is not callable.
    """
    for dotted_path in conf.get_setting(setting_key):
        validator = _get_validator(setting_key, dotted_path)
        validator(value)


def _get_validator(setting_key: str, dotted_path: str) -> Callable[[Any], None]:
    """Resolve ``dotted_path`` to a callable, importing and caching it on first use. Not part of
    this module's public surface."""
    cached = _resolved_validators.get(dotted_path)
    if cached is not None:
        return cached

    try:
        # import_string() is typed to return Any (django-stubs) — annotated here so the
        # function's own declared return type (Callable[[Any], None]) is honored on return,
        # not silently widened back to Any.
        candidate: Callable[[Any], None] = import_string(dotted_path)
    except ImportError as exc:
        raise ValidationError(
            f"{setting_key} names '{dotted_path}', which could not be imported."
        ) from exc

    if not callable(candidate):
        raise ValidationError(f"{setting_key} names '{dotted_path}', which is not callable.")

    _resolved_validators[dotted_path] = candidate
    return candidate
