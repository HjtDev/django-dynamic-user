"""Plain ``django.contrib.admin.ModelAdmin`` registrations for ``User``/``Profile``/``Setting``/
``AccountDeletionRequest``/``ChangeLogEntry``.

Jazzmin is **not** a dependency of this package; a host's own installed Jazzmin renders these
plain registrations, and this package never writes to ``JAZZMIN_SETTINGS`` itself
(``APP-DESIGN.md`` §5). Suggested ``JAZZMIN_SETTINGS["icons"]`` entries, for the README (Phase 9):

* ``dynamic_user.user`` — ``fas fa-user``
* ``dynamic_user.profile`` — ``fas fa-id-card``
* ``dynamic_user.setting`` — ``fas fa-sliders-h``
* ``dynamic_user.accountdeletionrequest`` — ``fas fa-user-slash``
* ``dynamic_user.changelogentry`` — ``fas fa-history``

Every model reference here is indirect — ``django.contrib.auth.get_user_model()`` for the user,
``dynamic_user.resolution.get_profile_model()``/``get_setting_model()`` for the other two — never
a concrete ``from dynamic_user.models import User/Profile/Setting`` import
(``docs/CONTRACT.md`` §0 item 1). ``AccountDeletionRequest``/``ChangeLogEntry`` are the two models
this package documents as **not** swappable, so importing them directly from ``dynamic_user.models``
is the correct, intended path for them specifically — see that module's own docstring.

Calling ``get_user_model()``/``resolution.get_profile_model()`` at this module's top level is
safe here in a way it would not be in ``models.py`` or ``apps.py``: ``admin.py`` is only ever
imported by ``django.contrib.admin``'s ``autodiscover()``, itself called from
``AdminConfig.ready()`` — by which point the whole app registry is populated and settings are
configured. This is the same timing ``django.contrib.auth.admin`` itself relies on.

**Why this module defines its own ``UserChangeForm``/``UserCreationForm``, not
``django.contrib.auth.forms``' stock ones.** Django's own ``UserChangeForm``/
``BaseUserCreationForm`` hardcode ``Meta.model = django.contrib.auth.models.User`` — the
*swapped-out* concrete model, not ``get_user_model()``. Subclassing
``django.contrib.auth.admin.UserAdmin`` without also overriding these two forms would build a
form bound to the wrong model the moment ``AUTH_USER_MODEL`` points anywhere else, which it always
does for this package. Re-pointing ``Meta.model`` at ``get_user_model()`` is the same fix every
Django project with a custom user model has to make.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.forms import AdminUserCreationForm as DjangoAdminUserCreationForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from dynamic_user import resolution
from dynamic_user.models import (
    AbstractDynamicUser,
    AbstractProfile,
    AbstractSetting,
    AccountDeletionRequest,
    ChangeLogEntry,
)
from dynamic_user.services import DeletionService, InvalidDeletionState

# django-stubs declares UserChangeForm/AdminUserCreationForm/UserAdmin/ModelAdmin as Generic —
# but only in the .pyi stub, never on the real runtime class (none of them define
# __class_getitem__, unlike e.g. QuerySet/Manager, which genuinely do). Subscripting one of
# these as a real base class — `class Foo(RealDjangoClass[Bar]):` — executes at import time and
# raises `TypeError: ... is not subscriptable`, verified live: this is what a first attempt at
# this file did, and it crashed `manage.py`/pytest's admin autodiscovery outright the moment
# admin.py was actually imported, not just under mypy.
#
# The fix every django-stubs-typed codebase facing this uses: subscript only inside a
# TYPE_CHECKING branch, so mypy sees the parametrized generic while the real interpreter never
# evaluates that expression at all — it takes the plain, unsubscripted class instead. Every
# parameter below is the ABSTRACT base (AbstractDynamicUser/AbstractProfile/AbstractSetting),
# never a concrete User/Profile/Setting — the type-checking equivalent of resolution.py's own
# runtime indirection. `Meta.model = get_user_model()` (below) is the actual runtime binding;
# these TYPE_CHECKING aliases are only what mypy checks statically.
if TYPE_CHECKING:
    _UserChangeFormBase = DjangoUserChangeForm[AbstractDynamicUser]
    _UserCreationFormBase = DjangoAdminUserCreationForm[AbstractDynamicUser]
    _UserAdminBase = DjangoUserAdmin[AbstractDynamicUser]
    _ProfileAdminBase = admin.ModelAdmin[AbstractProfile]
    _SettingAdminBase = admin.ModelAdmin[AbstractSetting]
    _DeletionRequestAdminBase = admin.ModelAdmin[AccountDeletionRequest]
    _ChangeLogEntryAdminBase = admin.ModelAdmin[ChangeLogEntry]
else:
    _UserChangeFormBase = DjangoUserChangeForm
    _UserCreationFormBase = DjangoAdminUserCreationForm
    _UserAdminBase = DjangoUserAdmin
    _ProfileAdminBase = admin.ModelAdmin
    _SettingAdminBase = admin.ModelAdmin
    _DeletionRequestAdminBase = admin.ModelAdmin
    _ChangeLogEntryAdminBase = admin.ModelAdmin


class UserChangeForm(_UserChangeFormBase):
    """``django.contrib.auth.forms.UserChangeForm``, re-pointed at the resolved user model."""

    class Meta(DjangoUserChangeForm.Meta):
        model = get_user_model()


class UserCreationForm(_UserCreationFormBase):
    """``django.contrib.auth.forms.AdminUserCreationForm``, re-pointed at the resolved user
    model. ``AdminUserCreationForm`` itself declares no ``Meta`` — it inherits
    ``BaseUserCreationForm.Meta`` (``fields = ("username",)``), which is exactly the field this
    app's ``USERNAME_FIELD`` names, so no ``fields`` override is needed here."""

    class Meta(DjangoAdminUserCreationForm.Meta):
        model = get_user_model()


@admin.register(get_user_model())
class UserAdmin(_UserAdminBase):
    """Subclasses Django's own ``UserAdmin`` for its ``add_view``/change-password-link
    machinery — ``password`` is never exposed as a plain form field, only through the standard
    "change password" link Django's own admin already implements. Never reinvented.
    """

    form = UserChangeForm
    add_form = UserCreationForm

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("name", "email", "phone")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "usable_password", "password1", "password2"),
            },
        ),
    )
    list_display = ("username", "email", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")
    search_fields = ("username", "email", "name", "phone")
    ordering = ("username",)
    readonly_fields = ("date_joined", "last_login")


@admin.register(resolution.get_profile_model())
class ProfileAdmin(_ProfileAdminBase):
    list_display = ("user", "is_public")
    list_filter = ("is_public",)
    search_fields = ("user__username", "user__email")

    def get_queryset(self, request: HttpRequest) -> QuerySet[AbstractProfile]:
        return super().get_queryset(request).select_related("user")


@admin.register(resolution.get_setting_model())
class SettingAdmin(_SettingAdminBase):
    list_display = ("user", "language", "timezone", "notifications_enabled")
    list_filter = ("language", "notifications_enabled")
    search_fields = ("user__username", "user__email")

    def get_queryset(self, request: HttpRequest) -> QuerySet[AbstractSetting]:
        return super().get_queryset(request).select_related("user")


@admin.action(description=_("Approve selected deletion requests"))
def approve_selected(
    modeladmin: AccountDeletionRequestAdmin,
    request: HttpRequest,
    queryset: QuerySet[AccountDeletionRequest],
) -> None:
    """Calls ``DeletionService.review(approved=True)`` per selected row — never a raw
    ``queryset.update()``, so each row goes through the same state-machine/signal path a real
    admin API call would (``docs/CONTRACT.md`` §5's own instruction for this action)."""
    _review_selected(request, queryset, approved=True)


@admin.action(description=_("Reject selected deletion requests"))
def reject_selected(
    modeladmin: AccountDeletionRequestAdmin,
    request: HttpRequest,
    queryset: QuerySet[AccountDeletionRequest],
) -> None:
    """Calls ``DeletionService.review(approved=False)`` per selected row — see
    :func:`approve_selected`."""
    _review_selected(request, queryset, approved=False)


def _review_selected(
    request: HttpRequest, queryset: QuerySet[AccountDeletionRequest], *, approved: bool
) -> None:
    """Shared implementation behind :func:`approve_selected`/:func:`reject_selected` — not part
    of this module's public surface. A row that isn't currently ``PENDING`` (e.g. already
    reviewed by someone else since the changelist was loaded) reports an error for that row and
    continues with the rest, rather than aborting the whole action."""
    reviewed, skipped = 0, 0
    # django-stubs types HttpRequest.user as `User | AnonymousUser`; this action is only ever
    # reachable through a real Django admin changelist, which already requires an authenticated,
    # permitted user before a single action runs — AnonymousUser genuinely cannot reach here.
    reviewer = cast(AbstractBaseUser, request.user)
    for deletion_request in queryset:
        try:
            DeletionService.review(deletion_request.pk, approved=approved, reviewed_by=reviewer)
        except InvalidDeletionState as exc:
            skipped += 1
            messages.error(request, str(exc))
        else:
            reviewed += 1

    if reviewed:
        if approved:
            text = ngettext(
                "%(count)d deletion request approved.",
                "%(count)d deletion requests approved.",
                reviewed,
            )
        else:
            text = ngettext(
                "%(count)d deletion request rejected.",
                "%(count)d deletion requests rejected.",
                reviewed,
            )
        messages.success(request, text % {"count": reviewed})
    if skipped:
        text = ngettext(
            "%(count)d deletion request skipped — see errors above.",
            "%(count)d deletion requests skipped — see errors above.",
            skipped,
        )
        messages.warning(request, text % {"count": skipped})


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(_DeletionRequestAdminBase):
    list_display = ("user", "status", "requested_at", "finalize_at", "reviewed_by")
    list_filter = ("status",)
    readonly_fields = ("requested_at", "reviewed_at")
    search_fields = ("user__username", "user__email")
    actions = (approve_selected, reject_selected)

    def get_queryset(self, request: HttpRequest) -> QuerySet[AccountDeletionRequest]:
        return super().get_queryset(request).select_related("user", "reviewed_by")


@admin.register(ChangeLogEntry)
class ChangeLogEntryAdmin(_ChangeLogEntryAdminBase):
    list_display = ("content_type", "object_id", "field_name", "actor", "changed_at")
    list_filter = ("content_type",)
    readonly_fields = (
        "content_type",
        "object_id",
        "actor",
        "field_name",
        "old_value",
        "new_value",
        "changed_at",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[ChangeLogEntry]:
        return super().get_queryset(request).select_related("content_type", "actor")

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Change-log rows are written only by HistoryMixin.log_change() — never hand-created.
        return False
