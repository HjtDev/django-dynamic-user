"""Settings access layer for this app's ``DYNAMIC_USER`` settings dict.

Every module in this package reads its configuration through :func:`get_setting` (or, for
``USER_PRIVILEGED_FIELDS`` specifically, :func:`get_privileged_fields` — see below), never a
scattered ``getattr(settings, ...)`` call (``APP-DESIGN.md`` §3.5) — so a host that omits an
optional key gets this app's documented default instead of an ``AttributeError`` deep in a view.

Plus **two top-level** settings, alongside ``AUTH_USER_MODEL``, not ``DYNAMIC_USER`` keys —
because Django's ``swappable_dependency()`` machinery expects a top-level setting name:

* ``DYNAMIC_USER_PROFILE_MODEL`` — ``"app_label.ModelName"``, defaults to
  ``"dynamic_user.Profile"`` if unset, but a host is expected to set it explicitly
  (``resolution.py``/``checks.py`` validate it either way).
* ``DYNAMIC_USER_SETTING_MODEL`` — same, defaults to ``"dynamic_user.Setting"``.

Twenty keys, all optional at the Python level (``docs/CONTRACT.md`` §6)::

    DYNAMIC_USER = {
        "USER_READ_FIELDS": ["id", "username", "name", "email", "phone", "is_active",
                              "date_joined"],
        # Fields on GET /me/ and the admin user read views (admin gets the full model
        # regardless via a separate full-fields build).
        "USER_EDITABLE_FIELDS": ["name", "phone"],
        # Fields writable via a future self-service /me/ PATCH — currently unused since
        # GET /me/ is read-only and admin PATCH builds from the model's full field set via
        # get_admin_user_serializer(), not this allowlist. Kept for forward-compat.
        "USER_LOCKED_FIELDS": ["username", "email", "is_staff", "is_superuser", "is_active"],
        # Subtracted from USER_EDITABLE_FIELDS at build time even if a host also lists one of
        # these there — belt-and-braces, deterministic.
        "USER_PUBLIC_FIELDS": ["id", "username"],
        # Fields on the nested `user` block of a public profile response.
        "USER_PRIVILEGED_FIELDS": ["is_staff", "is_superuser", "is_active", "groups",
                                    "user_permissions"],
        # The exact set CanEscalatePrivilege gates. A host may ADD to this set but the
        # resolved value is always DEFAULT UNION host's — read through get_privileged_fields(),
        # never get_setting(), so the floor can never be shrunk.
        "PROFILE_READ_FIELDS": ["id", "bio", "is_public"],
        # Fields on GET /me/profile/.
        "PROFILE_EDITABLE_FIELDS": ["bio", "is_public"],
        # Fields on PATCH /me/profile/.
        "PROFILE_PUBLIC_FIELDS": ["id", "bio"],
        # Fields on /profiles/, /profiles/{id}/ — deliberately minimal.
        "SETTING_READ_FIELDS": ["id", "language", "timezone", "notifications_enabled"],
        # Fields on GET /me/setting/.
        "SETTING_EDITABLE_FIELDS": ["language", "timezone", "notifications_enabled"],
        # Fields on PATCH /me/setting/.
        "PHONE_VALIDATORS": [],
        # Dotted callable paths, resolved lazily and cached on first use by
        # validators.run_validators("PHONE_VALIDATORS", value). Empty = no extra validation
        # beyond Django's own field checks — no opinionated phone format shipped.
        "NAME_VALIDATORS": [],
        # Same shape, for `name`.
        "ADMIN_REQUIRES_SUPERUSER": False,
        # True tightens every admin gate from is_staff to is_superuser. Never loosens
        # CanEscalatePrivilege or the deletion-finalize gate.
        "AUTO_CREATE_PROFILE": True,
        # Connects the User post_save(created=True) receiver that calls
        # get_profile_model().objects.get_or_create(user=instance) and sends profile_created.
        "AUTO_CREATE_SETTING": True,
        # Same, for Setting/setting_created.
        "DELETION_MODE": "hard_delete",
        # "hard_delete" or "anonymize".
        "DELETION_GRACE_PERIOD_DAYS": 14,
        # finalize_at = requested_at + this many days at DeletionService.request() time.
        "DELETION_ANONYMIZE_FUNCTION": None,
        # Dotted path to a callable (user) -> None, called by .finalize() when
        # DELETION_MODE="anonymize". None while DELETION_MODE="anonymize" is
        # ImproperlyConfigured at check time — fails closed, never silently falls back to
        # hard-delete.
        "DELETION_HISTORY_RETENTION_DAYS": 90,
        # Default window tasks.purge_deletion_history uses when not passed an explicit
        # older_than_days.
        "LAST_SEEN_UPDATE_SECONDS": 300,
        # Minimum interval LastSeenMixin's update path (a host-wired hook, not a view this
        # package ships) writes a new last_seen_at, to avoid a write per request.
    }

Zero ``.env`` keys, required or optional, under any installed extra (``docs/CONTRACT.md`` §6) —
this app configures entirely through ``DYNAMIC_USER`` plus the two top-level swappable-model
settings.
"""

from __future__ import annotations

from typing import Any, Final

from django.conf import settings

DEFAULTS: Final[dict[str, Any]] = {
    "USER_READ_FIELDS": ["id", "username", "name", "email", "phone", "is_active", "date_joined"],
    "USER_EDITABLE_FIELDS": ["name", "phone"],
    "USER_LOCKED_FIELDS": ["username", "email", "is_staff", "is_superuser", "is_active"],
    "USER_PUBLIC_FIELDS": ["id", "username"],
    "USER_PRIVILEGED_FIELDS": [
        "is_staff",
        "is_superuser",
        "is_active",
        "groups",
        "user_permissions",
    ],
    "PROFILE_READ_FIELDS": ["id", "bio", "is_public"],
    "PROFILE_EDITABLE_FIELDS": ["bio", "is_public"],
    "PROFILE_PUBLIC_FIELDS": ["id", "bio"],
    "SETTING_READ_FIELDS": ["id", "language", "timezone", "notifications_enabled"],
    "SETTING_EDITABLE_FIELDS": ["language", "timezone", "notifications_enabled"],
    "PHONE_VALIDATORS": [],
    "NAME_VALIDATORS": [],
    "ADMIN_REQUIRES_SUPERUSER": False,
    "AUTO_CREATE_PROFILE": True,
    "AUTO_CREATE_SETTING": True,
    "DELETION_MODE": "hard_delete",
    "DELETION_GRACE_PERIOD_DAYS": 14,
    "DELETION_ANONYMIZE_FUNCTION": None,
    "DELETION_HISTORY_RETENTION_DAYS": 90,
    "LAST_SEEN_UPDATE_SECONDS": 300,
}

#: The two top-level swappable-model settings (never DYNAMIC_USER keys — Django's
#: swappable_dependency() machinery expects a top-level setting name). Read directly by
#: resolution.py, not through get_setting(); listed here only as the documented defaults.
PROFILE_MODEL_DEFAULT: Final[str] = "dynamic_user.Profile"
SETTING_MODEL_DEFAULT: Final[str] = "dynamic_user.Setting"


def get_setting(key: str) -> Any:
    """Read a ``DYNAMIC_USER`` setting, falling back to this app's documented default.

    Do NOT use this for ``USER_PRIVILEGED_FIELDS`` — that key has union semantics
    (``docs/CONTRACT.md`` §6: "the resolved value is always DEFAULT UNION host's — the floor
    above can never be shrunk"), which a plain ``dict.get`` override would violate by letting a host
    shrink the privilege-escalation guard. Use :func:`get_privileged_fields` for that key.

    Raises:
        KeyError: only for a ``key`` that isn't in :data:`DEFAULTS` at all — a programming error
            inside this app itself, never a host-facing failure mode.
    """
    configured: dict[str, Any] = getattr(settings, "DYNAMIC_USER", {})
    return configured.get(key, DEFAULTS[key])


def get_privileged_fields() -> frozenset[str]:
    """Read ``DYNAMIC_USER["USER_PRIVILEGED_FIELDS"]`` with union, not override, semantics.

    A host may only ever ADD to the default privileged-field set, never remove from it —
    ``CanEscalatePrivilege`` (``docs/CONTRACT.md`` §5) gates exactly this set, and this repo's
    ``CLAUDE.md`` rule 3 makes shrinking it a defect, not a configuration choice. Returns
    ``DEFAULTS["USER_PRIVILEGED_FIELDS"] | {host's list}``, always.
    """
    configured: dict[str, Any] = getattr(settings, "DYNAMIC_USER", {})
    host_value = configured.get("USER_PRIVILEGED_FIELDS", [])
    return frozenset(DEFAULTS["USER_PRIVILEGED_FIELDS"]) | frozenset(host_value)
