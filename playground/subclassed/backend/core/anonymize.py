"""``DYNAMIC_USER["DELETION_ANONYMIZE_FUNCTION"]`` — the ``(user) -> None`` callable
``DeletionService.finalize()`` calls when ``DELETION_MODE="anonymize"`` (``config/settings.py``).
A host-owned decision: what "anonymized" means is never this package's business
(``docs/CONTRACT.md`` §6 — the setting is a dotted path precisely so a host supplies its own
policy). This one scrubs every directly-identifying field on ``core.User`` plus the Profile/Setting
free-text fields, and deactivates the account rather than leaving it live under a scrubbed
identity.
"""

from __future__ import annotations

from typing import Any


def anonymize_user(user: Any) -> None:
    user.username = f"deleted-user-{user.pk}"
    user.email = f"deleted-{user.pk}@anonymized.invalid"
    user.phone = None
    user.name = ""
    user.department = ""
    user.is_active = False
    user.set_unusable_password()
    user.save()

    profile = getattr(user, "profile", None)
    if profile is not None:
        profile.bio = ""
        profile.tagline = ""
        profile.is_public = False
        profile.save(update_fields=["bio", "tagline", "is_public"])
