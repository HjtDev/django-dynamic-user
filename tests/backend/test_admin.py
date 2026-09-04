"""Exercises the ``ModelAdmin`` registrations in ``dynamic_user.admin`` — real Django admin
changelists/actions via ``django.test.Client.force_login``, not appkit's DRF-oriented
``force_authenticate`` (which only affects DRF's own request wrapping, never plain Django admin
views' ``request.user``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.test import Client
from django.urls import reverse
from django.utils import translation

from dynamic_user.admin import UserChangeForm
from dynamic_user.models import AccountDeletionRequest, ChangeLogEntry
from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = pytest.mark.django_db

MO_PATH = (
    Path(__file__).resolve().parents[2] / "backend/src/dynamic_user/locale/fa/LC_MESSAGES/django.mo"
)


def test_user_setting_profile_deletion_changelog_are_all_registered() -> None:
    registry = admin.site._registry
    assert get_user_model() in registry
    assert get_profile_model() in registry
    assert get_setting_model() in registry
    assert AccountDeletionRequest in registry
    assert ChangeLogEntry in registry


def test_user_admin_changelist_reachable_by_superuser(client: Client, admin_user: object) -> None:
    client.force_login(admin_user)
    url = reverse("admin:dynamic_user_user_changelist")
    response = client.get(url)
    assert response.status_code == 200


def test_user_admin_changelist_not_reachable_by_anonymous(client: Client) -> None:
    url = reverse("admin:dynamic_user_user_changelist")
    response = client.get(url)
    assert response.status_code in (302, 403)


def test_user_change_form_exposes_password_only_via_readonly_hash_field(user: object) -> None:
    form = UserChangeForm(instance=user)
    assert isinstance(form.fields["password"], ReadOnlyPasswordHashField)


def test_user_change_form_is_bound_to_resolved_user_model() -> None:
    assert UserChangeForm.Meta.model is get_user_model()


def test_profile_admin_queryset_is_select_related(admin_user: object) -> None:
    profile_admin = admin.site._registry[get_profile_model()]
    qs = profile_admin.get_queryset(_fake_request(admin_user))
    assert qs.query.select_related


def test_setting_admin_queryset_is_select_related(admin_user: object) -> None:
    setting_admin = admin.site._registry[get_setting_model()]
    qs = setting_admin.get_queryset(_fake_request(admin_user))
    assert qs.query.select_related


def test_deletion_request_admin_queryset_is_select_related(admin_user: object) -> None:
    deletion_admin = admin.site._registry[AccountDeletionRequest]
    qs = deletion_admin.get_queryset(_fake_request(admin_user))
    assert qs.query.select_related


def test_change_log_entry_admin_queryset_is_select_related(admin_user: object) -> None:
    changelog_admin = admin.site._registry[ChangeLogEntry]
    qs = changelog_admin.get_queryset(_fake_request(admin_user))
    assert qs.query.select_related


def test_change_log_entry_admin_disallows_add() -> None:
    changelog_admin = admin.site._registry[ChangeLogEntry]
    assert changelog_admin.has_add_permission(_fake_request(None)) is False


def test_approve_selected_action_approves_via_deletion_service(
    client: Client, admin_user: object, pending_deletion_request: AccountDeletionRequest
) -> None:
    client.force_login(admin_user)
    url = reverse("admin:dynamic_user_accountdeletionrequest_changelist")
    response = client.post(
        url,
        {
            "action": "approve_selected",
            "_selected_action": [str(pending_deletion_request.pk)],
        },
        follow=True,
    )
    assert response.status_code == 200
    pending_deletion_request.refresh_from_db()
    assert pending_deletion_request.status == AccountDeletionRequest.Status.APPROVED
    assert pending_deletion_request.reviewed_by_id == admin_user.pk


def test_reject_selected_action_rejects_via_deletion_service(
    client: Client, admin_user: object, pending_deletion_request: AccountDeletionRequest
) -> None:
    client.force_login(admin_user)
    url = reverse("admin:dynamic_user_accountdeletionrequest_changelist")
    response = client.post(
        url,
        {
            "action": "reject_selected",
            "_selected_action": [str(pending_deletion_request.pk)],
        },
        follow=True,
    )
    assert response.status_code == 200
    pending_deletion_request.refresh_from_db()
    assert pending_deletion_request.status == AccountDeletionRequest.Status.REJECTED


def test_approve_selected_action_on_already_reviewed_request_reports_error_not_crash(
    client: Client, admin_user: object, pending_deletion_request: AccountDeletionRequest
) -> None:
    pending_deletion_request.status = AccountDeletionRequest.Status.APPROVED
    pending_deletion_request.save(update_fields=["status"])

    client.force_login(admin_user)
    url = reverse("admin:dynamic_user_accountdeletionrequest_changelist")
    response = client.post(
        url,
        {
            "action": "approve_selected",
            "_selected_action": [str(pending_deletion_request.pk)],
        },
        follow=True,
    )
    # Never a raw queryset.update() silently "succeeding" — the action must report the row was
    # skipped rather than crash the whole request.
    assert response.status_code == 200
    messages = [str(m) for m in response.context["messages"]]
    assert any("skipped" in m for m in messages)


def _fake_request(acting_user: Any) -> Any:
    from django.test import RequestFactory

    request = RequestFactory().get("/")
    request.user = acting_user
    return request


# ------------------------------------------------------------------------------------ locale


def test_fa_catalog_is_compiled_on_disk() -> None:
    """A committed ``.po`` alone is not enough — CI's wheel-smoke-test looks for a real ``.mo``
    in the built wheel, and this asserts the source of truth for that is actually present.
    """
    assert MO_PATH.is_file()
    assert MO_PATH.stat().st_size > 0


def test_fa_translation_renders() -> None:
    with translation.override("fa"):
        assert str(translation.gettext("username")) == "نام کاربری"
        assert str(translation.gettext("Approve selected deletion requests")) == (
            "تأیید درخواست‌های حذف انتخاب‌شده"
        )
