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

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class AbstractDynamicUser(AbstractBaseUser, PermissionsMixin):
    """The abstract base a host subclasses to add project-specific fields to the user model
    itself. ``is_superuser``, ``groups``, and ``user_permissions`` come from
    :class:`~django.contrib.auth.models.PermissionsMixin` — not redeclared here.
    """

    username = models.CharField(_("username"), max_length=150, unique=True)
    name = models.CharField(_("name"), max_length=150, blank=True)
    email = models.EmailField(_("email address"), unique=True)
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
    REQUIRED_FIELDS = ["email"]  # noqa: RUF012 -- mirrors AbstractUser.REQUIRED_FIELDS's own shape

    class Meta:
        abstract = True
        verbose_name = _("user")
        verbose_name_plural = _("users")
        indexes = [  # noqa: RUF012 -- Django's Meta.indexes is inherently a plain list, not an
            # instance attribute a subclass ever mutates; ClassVar doesn't apply to Meta.
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
        ]

    def __str__(self) -> str:
        return self.username


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
