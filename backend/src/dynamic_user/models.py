"""Data models: ``AbstractDynamicUser``/``User``, ``AbstractProfile``/``Profile``,
``AbstractSetting``/``Setting``, ``AccountDeletionRequest``, and ``ChangeLogEntry``.

Implements all five exactly as ``docs/CONTRACT.md`` §1 specifies — abstract bases so a host can
subclass any of the three swappable models, plus a concrete default the host can also install
as-is. Every model in this module declares ``Meta.indexes`` for fields used in frequent filters,
ordering, or foreign key lookups (``APP-DESIGN.md`` §2's baseline query-optimization note).

Every FK/O2O-shaped reference anywhere in this module is ``settings.AUTH_USER_MODEL`` — never a
concrete ``User`` import, and never a reference to another app package's model
(``docs/CONTRACT.md`` §1: "Requires another app package: No"). This applies even to
``AccountDeletionRequest.user``/``.reviewed_by`` and ``ChangeLogEntry.actor``, despite ``User``
being defined in this same file — a swapped-in host subclass must be reachable through the exact
same indirection a completely separate app would have to use.

**``ChangeLogEntry`` placement — deviation from ``docs/CONTRACT.md`` §1's literal text, recorded
as §10 item 15.** The contract's own code block shows ``ChangeLogEntry`` inside the ``mixins.py``
section, but Django only auto-imports an app's ``models.py`` when building the app registry; a
concrete model defined in ``mixins.py`` would never be discovered/migrated unless something else
imports that module first. It therefore lives here, in ``models.py``, and
``mixins.HistoryMixin.log_change()`` reaches it through a function-local import
(``from dynamic_user.models import ChangeLogEntry``) — a placement change only, no field, name, or
index differs from what the contract specifies.

``AbstractProfile``/``AbstractSetting`` are also what ``checks.py``'s Phase-2-reserved
``dynamic_user.E004`` will validate a host's swapped model against — see that module's docstring.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.db.models.base import ModelBase
from django.utils.translation import gettext_lazy as _

from dynamic_user import conf, validators
from dynamic_user.usernames import generate_username

from .managers import UserManager

#: save()'s bounded retry budget for an in-process username collision the pre-flight check in
#: usernames.py missed (concurrent writer). Not a settings key — a host-visible knob here would
#: invite tuning a number that exists purely to make a 2^-64 fluke invisible, not to be reasoned
#: about.
_USERNAME_COLLISION_RETRIES = 5


class AbstractDynamicUser(AbstractBaseUser, PermissionsMixin):
    """The abstract base a host subclasses to add project-specific fields to the user model
    itself. ``is_superuser``, ``groups``, and ``user_permissions`` come from
    :class:`~django.contrib.auth.models.PermissionsMixin` — not redeclared here.

    **v1.1.0 — both ``email`` and ``phone`` are optional; at least one is required.** This is what
    lets an external auth app (``docs/CONTRACT.md`` §1, ``../django-jwt-multiauth``'s
    ``UserProvisioningService.get_or_create``) create a user knowing only a phone number or only
    an email — the shape a phone-OTP or email-OTP registration actually has at creation time. The
    floor is a DB-level :class:`~django.db.models.CheckConstraint` (below) — not merely a
    serializer or manager check — because that external provisioning path writes fields directly
    and calls plain ``.save()``, never this app's own :class:`~dynamic_user.managers.UserManager`
    or a serializer. ``username`` is auto-generated when omitted (:mod:`dynamic_user.usernames`),
    enforced the same way: in :meth:`save`, not only in a view.
    """

    username = models.CharField(_("username"), max_length=150, unique=True, blank=True)
    name = models.CharField(_("name"), max_length=150, blank=True)
    email = models.EmailField(_("email address"), unique=True, null=True, blank=True)
    phone = models.CharField(_("phone number"), max_length=32, unique=True, null=True, blank=True)
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    date_joined = models.DateTimeField(_("date joined"), auto_now_add=True)

    objects = UserManager()

    # The ONE sanctioned exception to "no settings-affecting class attribute" (this repo's
    # CLAUDE.md rule 2, docs/CONTRACT.md §0 item 2). Django's auth machinery reads these at
    # class-definition time, not request time — changing them is a schema-affecting decision a
    # host makes once, before its first `migrate`, never a DYNAMIC_USER runtime setting.
    USERNAME_FIELD = "username"
    # v1.1.0: [] , not ["email"] — email is no longer guaranteed to exist, so it can no longer be
    # a REQUIRED_FIELDS entry (createsuperuser's own prompt loop would demand a value this model
    # doesn't actually require). This only loosens what createsuperuser prompts for; a host that
    # overrode REQUIRED_FIELDS itself is unaffected.
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta:
        abstract = True
        verbose_name = _("user")
        verbose_name_plural = _("users")
        indexes = [  # noqa: RUF012 -- Django's Meta.indexes is inherently a plain list, not an
            # instance attribute a subclass ever mutates; ClassVar doesn't apply to Meta.
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
        ]
        constraints = [  # noqa: RUF012 -- see the indexes note directly above
            models.CheckConstraint(
                # condition=, not check= — check= was removed in Django 6.0; this repo's
                # declared range is django>=5.2,<7.0, so condition= is the one spelling that
                # works across the whole range.
                condition=models.Q(email__isnull=False) | models.Q(phone__isnull=False),
                name="%(app_label)s_%(class)s_email_or_phone",
            ),
        ]

    def __str__(self) -> str:
        return self.username

    def _normalize_identity(self) -> None:
        """Coerce an empty-string ``email``/``phone`` to ``None`` — what makes ``unique=True``
        safe on both. Without this, a second row saved with ``phone=""`` (what an omitted
        ``CharField`` becomes coming out of a form/serializer, as opposed to ``None``) would
        raise ``IntegrityError`` on the unique index instead of being treated as "no phone", the
        same as a second row with ``email=""`` would today. Called from both :meth:`clean` and
        :meth:`save` — not part of this model's public surface."""
        if self.email == "":
            self.email = None
        if self.phone == "":
            self.phone = None

    def _ensure_username(self) -> None:
        """Fill a missing ``username`` — the OTP/OAuth registration case, where no username was
        ever supplied. Raises :exc:`~django.core.exceptions.ValidationError` instead of
        generating one when a host has set ``DYNAMIC_USER["USERNAME_AUTO_GENERATE"] = False``.
        Not part of this model's public surface."""
        if self.username:
            return
        if not conf.get_setting("USERNAME_AUTO_GENERATE"):
            raise ValidationError(
                {"username": _("This field is required.")}, code="username_required"
            )
        self.username = generate_username(type(self))

    def _validate_identity(self) -> None:
        """Raise :exc:`~django.core.exceptions.ValidationError` unless at least one of ``email``/
        ``phone`` is set, then run any configured ``PHONE_VALIDATORS``/``NAME_VALIDATORS``. This
        is the model-layer enforcement of ``docs/CONTRACT.md`` §1's identity rule — the DB
        :class:`~django.db.models.CheckConstraint` on ``Meta`` is what makes it unbypassable even
        by a caller that skips this method entirely (e.g. ``bulk_create``, raw SQL through the
        ORM). Not part of this model's public surface."""
        if self.email is None and self.phone is None:
            raise ValidationError(
                _("At least one of email or phone must be provided."),
                code="email_or_phone_required",
            )
        if self.phone:
            validators.run_validators("PHONE_VALIDATORS", self.phone)
        if self.name:
            validators.run_validators("NAME_VALIDATORS", self.name)

    def clean(self) -> None:
        super().clean()
        self._normalize_identity()
        self._ensure_username()
        self._validate_identity()

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Normalizes ``email``/``phone``, fills a missing ``username``, and enforces the
        email-or-phone rule — the layer that matters, because an external provisioning path
        (``docs/CONTRACT.md`` §1) writes fields directly and calls plain ``.save()``, never
        :class:`~dynamic_user.managers.UserManager` or a serializer. Retries once per collision
        (bounded, :data:`_USERNAME_COLLISION_RETRIES`) if a generated username loses a race with a
        concurrent insert — the DB's unique index is the real guarantee;
        :mod:`dynamic_user.usernames`'s own pre-save check is only a courtesy.

        When ``update_fields`` is given and touches neither ``email`` nor ``phone``, the
        both-null check is skipped — the row already satisfies the constraint, and
        ``django.contrib.auth.models.update_last_login`` calls exactly this shape
        (``save(update_fields=["last_login"])``) on every login.
        """
        self._normalize_identity()

        generated_username = False
        if not self.username:
            self._ensure_username()
            generated_username = True
        if update_fields is not None and generated_username:
            update_fields = [*update_fields, "username"]

        identity_fields_touched = update_fields is None or bool(
            set(update_fields) & {"email", "phone"}
        )
        if identity_fields_touched:
            self._validate_identity()

        attempts_left = _USERNAME_COLLISION_RETRIES
        while True:
            try:
                super().save(
                    force_insert=force_insert,
                    force_update=force_update,
                    using=using,
                    update_fields=update_fields,
                )
            except IntegrityError as exc:
                if generated_username and attempts_left > 1 and "username" in str(exc).lower():
                    attempts_left -= 1
                    self.username = generate_username(type(self))
                    continue
                raise
            else:
                return


class User(AbstractDynamicUser):
    class Meta(AbstractDynamicUser.Meta):
        swappable = "AUTH_USER_MODEL"


class AbstractProfile(models.Model):
    """The abstract base a host subclasses to add project-specific profile fields. No avatar
    field here by design (``docs/CONTRACT.md`` §1/§10 item 4) — :class:`dynamic_user.mixins.
    AvatarMixin` is opt-in, composed by a host that wants one, so the ``[avatar]`` extra never
    becomes a de facto hard dependency for every host.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="profile",
    )
    bio = models.TextField(_("bio"), blank=True)
    is_public = models.BooleanField(
        _("public"),
        default=True,
        help_text=_("Whether this profile is visible to other users."),
    )

    class Meta:
        abstract = True
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")

    def __str__(self) -> str:
        return f"Profile<{self.user_id}>"


class Profile(AbstractProfile):
    class Meta(AbstractProfile.Meta):
        swappable = "DYNAMIC_USER_PROFILE_MODEL"


class AbstractSetting(models.Model):
    """The abstract base a host subclasses to add project-specific preferences. Deliberately
    minimal — a host's own subclass is where project-specific preferences go."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="setting",
    )
    language = models.CharField(_("language"), max_length=10, default="en")
    timezone = models.CharField(_("timezone"), max_length=64, default="UTC")
    notifications_enabled = models.BooleanField(
        _("notifications enabled"),
        default=True,
        help_text=_("Whether this user receives notifications."),
    )

    class Meta:
        abstract = True
        verbose_name = _("setting")
        verbose_name_plural = _("settings")

    def __str__(self) -> str:
        return f"Setting<{self.user_id}>"


class Setting(AbstractSetting):
    class Meta(AbstractSetting.Meta):
        swappable = "DYNAMIC_USER_SETTING_MODEL"


class AccountDeletionRequest(models.Model):
    """Not swappable — a host extending this shape is expected to be rare enough that
    ``DYNAMIC_USER``'s deletion settings already cover it; no
    ``DYNAMIC_USER_DELETION_REQUEST_MODEL`` is introduced."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        FINALIZED = "finalized", _("Finalized")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name="deletion_requests",
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    reason = models.TextField(
        _("reason"), blank=True, help_text=_("Optional reason provided by the user.")
    )
    requested_at = models.DateTimeField(_("requested at"), auto_now_add=True)
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("reviewed by"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_deletion_requests",
    )
    finalize_at = models.DateTimeField(_("finalize at"), null=True, blank=True)

    class Meta:
        verbose_name = _("account deletion request")
        verbose_name_plural = _("account deletion requests")
        indexes = [  # noqa: RUF012 -- see AbstractDynamicUser.Meta's own indexes above
            models.Index(fields=["status", "finalize_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"AccountDeletionRequest<{self.pk}, {self.status}>"


class ChangeLogEntry(models.Model):
    """Concrete, always-migrated change-log row written by
    :meth:`dynamic_user.mixins.HistoryMixin.log_change`. Not swappable — a generic log table has
    no reason to vary per host. The only model in this package touching
    ``django.contrib.contenttypes`` (the ships-with-Django exception, ``docs/CONTRACT.md`` §0).
    See this module's docstring for why it lives here rather than in ``mixins.py``.
    """

    content_type = models.ForeignKey(
        "contenttypes.ContentType", verbose_name=_("content type"), on_delete=models.CASCADE
    )
    object_id = models.PositiveBigIntegerField(_("object id"))
    content_object = GenericForeignKey("content_type", "object_id")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("actor"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("The user who made this change, if known."),
    )
    field_name = models.CharField(_("field name"), max_length=100)
    old_value = models.TextField(_("old value"), blank=True)
    new_value = models.TextField(_("new value"), blank=True)
    changed_at = models.DateTimeField(_("changed at"), auto_now_add=True)

    class Meta:
        verbose_name = _("change log entry")
        verbose_name_plural = _("change log entries")
        # See AbstractDynamicUser.Meta's own indexes for why this noqa is here.
        indexes = [models.Index(fields=["content_type", "object_id"])]  # noqa: RUF012

    def __str__(self) -> str:
        return f"ChangeLogEntry<{self.content_type_id}:{self.object_id}, {self.field_name}>"
