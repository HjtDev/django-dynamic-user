"""Composable abstract-model mixin library.

One composable abstract model per mixin, each documenting exactly which fields it adds and any
requirement it places on the composing model (``docs/CONTRACT.md`` §1):

* ``AvatarMixin`` — an avatar ``ImageField``, behind the ``avatar`` extra at runtime only.
* ``TimestampMixin`` — ``created_at``/``updated_at``. No ``Meta`` requirement on the composing
  model.
* ``HistoryMixin`` — a generic-relation change log via
  :class:`dynamic_user.models.ChangeLogEntry`, the one place this package uses
  ``django.contrib.contenttypes`` (a ships-with-Django exception, not an app-package boundary
  concern per this repo's ``CLAUDE.md`` rule 4).
* ``SoftDeleteMixin`` — a soft-delete flag and manager swap.
* ``VerificationMixin`` — verified/unverified flags and timestamps.
* ``LastSeenMixin`` — ``last_seen_at``/``last_seen_ip``, updated no more often than
  ``DYNAMIC_USER["LAST_SEEN_UPDATE_SECONDS"]`` by a host-wired hook (not a view this package
  ships).
* ``MetadataMixin`` — a ``JSONField`` escape hatch for host-specific, unstructured data that
  doesn't warrant a real column. Never read or written by this package's own views/serializers
  by default — a host opts a field allowlist into it explicitly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.db import models
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


class AvatarMixin(models.Model):
    """Adds ``avatar``, ``avatar_updated_at``.

    Needs the ``[avatar]`` extra (Pillow, via ``hjtdev-appkit[images]``) only if the composing
    model is actually used — this mixin's own import never requires Pillow to be installed; only
    saving/validating an uploaded file does, via ``appkit.files.validate_image``. Not composed
    into ``AbstractProfile`` by default (``docs/CONTRACT.md`` §10 item 4): a host that wants an
    avatar composes it itself, e.g. ``class Profile(AbstractProfile, AvatarMixin): ...``.
    """

    avatar = models.ImageField(
        _("avatar"),
        upload_to="dynamic_user/avatars/",
        blank=True,
        null=True,
        help_text=_("Profile picture."),
    )
    avatar_updated_at = models.DateTimeField(_("avatar updated at"), null=True, blank=True)

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    """Adds ``created_at``/``updated_at``. No ``Meta`` requirement on the composing model."""

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class HistoryMixin(models.Model):
    """Adds nothing to the composing model's own fields — provides
    :meth:`log_change`, which writes a :class:`dynamic_user.models.ChangeLogEntry` row via a
    ``GenericForeignKey``. The ONLY place this package touches ``contenttypes``.

    The composing model needs no extra ``Meta`` of its own; ``ChangeLogEntry`` is a concrete,
    always-migrated model (not swappable — a generic log table has no reason to vary per host),
    already registered by ``models.py`` the moment this app is installed.
    """

    class Meta:
        abstract = True

    def log_change(
        self, field: str, old: Any, new: Any, *, actor: AbstractBaseUser | None = None
    ) -> None:
        """Write one :class:`~dynamic_user.models.ChangeLogEntry` row recording ``field``
        changing from ``old`` to ``new`` on this instance, optionally attributed to ``actor``.

        ``old``/``new`` are stored via ``str()`` — ``ChangeLogEntry.old_value``/``new_value`` are
        plain ``TextField``s, since the composing model's fields may be of any type a host adds.
        """
        from django.contrib.contenttypes.models import ContentType

        from dynamic_user.models import ChangeLogEntry

        ChangeLogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(self),
            object_id=self.pk,
            # Same django-stubs/AbstractBaseUser mismatch documented in services.py's own
            # DeletionService.review — actor's Python type here is pinned to this settings
            # module's concrete AUTH_USER_MODEL, never the abstract type this method's own
            # signature intentionally accepts.
            actor=cast(Any, actor),
            field_name=field,
            old_value="" if old is None else str(old),
            new_value="" if new is None else str(new),
        )


class SoftDeleteMixin(models.Model):
    """Adds ``is_deleted``, ``deleted_at``.

    Requirement on the composing model, stated explicitly because it cannot be auto-provided by
    the mixin: the composing model must define its own ``objects`` (filtered to
    ``is_deleted=False``) and ``all_objects`` (unfiltered) managers — a mixin cannot safely inject
    a manager onto ``User``, since ``User`` already needs :class:`dynamic_user.managers.
    UserManager` for ``AbstractBaseUser``'s own machinery, and Django resolves exactly one default
    manager.
    """

    is_deleted = models.BooleanField(
        _("deleted"), default=False, help_text=_("Whether this row is soft-deleted.")
    )
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        abstract = True


class VerificationMixin(models.Model):
    """Flags + timestamps only — no delivery logic. Sending a verification code is an
    auth-app's or host's job; this mixin just gives it somewhere to record the result."""

    email_verified = models.BooleanField(_("email verified"), default=False)
    email_verified_at = models.DateTimeField(_("email verified at"), null=True, blank=True)
    phone_verified = models.BooleanField(_("phone verified"), default=False)
    phone_verified_at = models.DateTimeField(_("phone verified at"), null=True, blank=True)

    class Meta:
        abstract = True


class LastSeenMixin(models.Model):
    """Adds ``last_seen_at``, ``last_seen_ip``. No ``Meta`` requirement on the composing model —
    the write-throttling described in ``DYNAMIC_USER["LAST_SEEN_UPDATE_SECONDS"]`` is a host-wired
    hook's responsibility, not something this mixin enforces itself."""

    last_seen_at = models.DateTimeField(_("last seen at"), null=True, blank=True)
    last_seen_ip = models.GenericIPAddressField(_("last seen IP"), null=True, blank=True)

    class Meta:
        abstract = True


class MetadataMixin(models.Model):
    """A ``JSONField`` escape hatch for host-specific, unstructured data that doesn't warrant a
    real column. Never read or written by this package's own views/serializers by default — a
    host opts a field allowlist into it explicitly."""

    metadata = models.JSONField(
        _("metadata"), default=dict, blank=True, help_text=_("Unstructured host-specific data.")
    )

    class Meta:
        abstract = True
