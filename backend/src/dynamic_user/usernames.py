"""Username generation for a user created without one — the OTP/OAuth registration case
``docs/CONTRACT.md`` §1 documents: a phone-OTP or email-OTP registration knows only one identity
field at creation time, never a username.

:func:`generate_username` is called from ``AbstractDynamicUser.save()`` (``models.py``), never a
view or a serializer directly — the same "the model layer is the one place this rule can't be
bypassed" reasoning as the email-or-phone ``CheckConstraint`` it sits alongside.

Resolution order, mirroring ``validators._get_validator``'s fail-closed shape exactly:

1. ``DYNAMIC_USER["USERNAME_AUTO_GENERATE"]`` is ``False`` — raise, never silently proceed with a
   blank username past this point (``save()`` itself decides whether to call in here at all; this
   module only implements *how*, not *whether*).
2. ``DYNAMIC_USER["USERNAME_GENERATOR"]`` is set — resolve it via
   ``django.utils.module_loading.import_string``, cache the resolved callable (never the setting
   value itself, matching ``validators.py``'s own split), and call it with the model class. Not
   callable or unimportable both raise ``ImproperlyConfigured`` naming the dotted path — fail
   closed, never a silent fallback to the built-in generator.
3. Otherwise, the built-in generator: ``f"{DYNAMIC_USER['USERNAME_PREFIX']}{secrets.token_hex(8)}"``
   — 64 bits of ``secrets`` randomness, not ``random``, checked against the resolved model's own
   table for a collision up to 10 times before giving up. This is a courtesy check, not the
   uniqueness guarantee: the DB's own unique index on ``username`` is what actually enforces
   uniqueness, and ``AbstractDynamicUser.save()`` retries on the rare ``IntegrityError`` this loop
   fails to avoid.
"""

from __future__ import annotations

import secrets
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.utils.module_loading import import_string

from dynamic_user import conf

_MAX_COLLISION_RETRIES = 10

#: Cache of resolved generator callables, keyed by dotted path — mirrors
#: ``validators._resolved_validators``'s "cache the callable, not the setting" split.
_resolved_generators: dict[str, Any] = {}


def generate_username(model: type[Model]) -> str:
    """Return a username not currently in use by ``model``'s table.

    Raises:
        ImproperlyConfigured: ``USERNAME_GENERATOR`` names a dotted path that can't be imported,
            or that isn't callable.
    """
    dotted_path = conf.get_setting("USERNAME_GENERATOR")
    if dotted_path:
        generator = _get_generator(dotted_path)
        return str(generator(model))
    return _generate_builtin(model)


def _get_generator(dotted_path: str) -> Any:
    """Not part of this module's public surface — resolve and cache ``dotted_path``, failing
    closed on anything but a genuinely callable target."""
    cached = _resolved_generators.get(dotted_path)
    if cached is not None:
        return cached

    try:
        candidate = import_string(dotted_path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f'DYNAMIC_USER["USERNAME_GENERATOR"] names "{dotted_path}", '
            "which could not be imported."
        ) from exc

    if not callable(candidate):
        raise ImproperlyConfigured(
            f'DYNAMIC_USER["USERNAME_GENERATOR"] names "{dotted_path}", which is not callable.'
        )

    _resolved_generators[dotted_path] = candidate
    return candidate


def _generate_builtin(model: type[Model]) -> str:
    """Not part of this module's public surface — ``USERNAME_PREFIX`` + 16 hex chars of
    ``secrets`` randomness, retried on an in-process collision. The DB's unique index, not this
    loop, is what actually guarantees uniqueness against a concurrent writer."""
    prefix = conf.get_setting("USERNAME_PREFIX")
    manager = model._default_manager
    for _ in range(_MAX_COLLISION_RETRIES):
        candidate = f"{prefix}{secrets.token_hex(8)}"
        if not manager.filter(username=candidate).exists():
            return candidate
    # Astronomically unlikely (64 bits of entropy) — one more candidate, unchecked, rather than
    # raising and turning a one-in-2^64 fluke into a hard registration failure. save()'s own
    # IntegrityError retry is the real backstop if this one somehow collides too.
    return f"{prefix}{secrets.token_hex(8)}"
