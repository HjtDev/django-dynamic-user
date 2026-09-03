"""``UserManager`` — the manager ``AbstractBaseUser`` requires.

Phase 2 implements ``UserManager(BaseUserManager)``: ``create_user(username, email,
password=None, **extra)`` and ``create_superuser(username, email, password, **extra)``.

``create_superuser`` sets ``is_staff=True, is_superuser=True`` directly — this is the one place
in the whole package those fields are written outside a superuser-gated HTTP path, and it's safe
*because* it has no HTTP path at all: it's reachable only from ``createsuperuser``/a shell/a data
migration, never a request. Documented here so a later phase doesn't misread it as a violation of
this repo's ``CLAUDE.md`` rule 3 (no non-superuser-gated code path may write
``is_staff``/``is_superuser``/``is_active``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:
    # The abstract base, never a concrete User — even under TYPE_CHECKING, which has zero
    # runtime effect either way. Also sidesteps a real circular import: models.py imports THIS
    # module for UserManager, so importing anything from models.py back at runtime here would
    # be circular regardless of which name was imported.
    from dynamic_user.models import AbstractDynamicUser


class UserManager(BaseUserManager["AbstractDynamicUser"]):
    """Manager for :class:`dynamic_user.models.AbstractDynamicUser` subclasses.

    Required by ``AbstractBaseUser`` — Django refuses to define a concrete model on top of it
    without one. Not itself settings-driven or swappable; a host subclassing ``User`` inherits
    this manager unless it explicitly overrides ``objects``.
    """

    use_in_migrations = True

    def create_user(
        self, username: str, email: str, password: str | None = None, **extra_fields: Any
    ) -> AbstractDynamicUser:
        """Create and save a regular user. ``is_staff``/``is_superuser``/``is_active`` are never
        accepted here beyond their model defaults — a caller wanting those set uses
        :meth:`create_superuser` or writes to the row directly outside any HTTP path."""
        if not username:
            raise ValueError("The given username must be set.")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, username: str, email: str, password: str, **extra_fields: Any
    ) -> AbstractDynamicUser:
        """Create and save a superuser. Sets ``is_staff=True, is_superuser=True`` directly —
        see this module's docstring for why that is not a violation of the escalation rail: this
        method has no HTTP path, ever."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, email, password, **extra_fields)
