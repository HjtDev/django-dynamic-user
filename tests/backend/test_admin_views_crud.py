"""v1.1.0's admin/API parity additions — the DEFAULT-models leg.

Covers every new admin endpoint: user create/delete/set-password, the profiles/settings
collections, the deletion-request detail/create/cancel routes, change-log, log-entries, and the
read-only groups/permissions surfaces. Follows ``test_admin_views.py``'s own established pattern:
permission checks proven by actual attempt, not by reading the permission class.
"""

from __future__ import annotations

from typing import Any

import pytest
from appkit.testing import appkit_assert_error_envelope
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from dynamic_user.models import AccountDeletionRequest, ChangeLogEntry
from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = pytest.mark.django_db


@pytest.fixture
def client(user: Any) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def staff_client(staff_user: Any) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=staff_user)
    return api_client


@pytest.fixture
def admin_client(admin_user: Any) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=admin_user)
    return api_client


# ------------------------------------------------------------------------------- POST / (create)


def test_staff_admin_can_create_a_user(staff_client: APIClient) -> None:
    response = staff_client.post(
        reverse("dynamic-user-admin-user-list"),
        {"username": "created1", "email": "created1@example.com", "password": "s3cret-pw!"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["username"] == "created1"
    assert "password" not in response.data


def test_create_user_with_no_password_is_unusable(staff_client: APIClient) -> None:
    from django.contrib.auth import get_user_model

    response = staff_client.post(
        reverse("dynamic-user-admin-user-list"),
        {"username": "created2", "email": "created2@example.com"},
        format="json",
    )
    assert response.status_code == 201
    created = get_user_model().objects.get(pk=response.data["id"])
    assert created.has_usable_password() is False


def test_create_user_with_neither_email_nor_phone_is_400(staff_client: APIClient) -> None:
    response = staff_client.post(
        reverse("dynamic-user-admin-user-list"), {"username": "ghost"}, format="json"
    )
    assert response.status_code == 400


def test_staff_admin_cannot_create_a_superuser(staff_client: APIClient) -> None:
    """CanEscalatePrivilege gates POST / exactly like PATCH /{id}/ — whole request rejected."""
    from django.contrib.auth import get_user_model

    response = staff_client.post(
        reverse("dynamic-user-admin-user-list"),
        {
            "username": "escalated",
            "email": "escalated@example.com",
            "password": "pw",
            "is_superuser": True,
        },
        format="json",
    )
    appkit_assert_error_envelope(response, code="permission_denied", status=403)
    assert not get_user_model().objects.filter(username="escalated").exists()


def test_superuser_can_create_a_staff_user(admin_client: APIClient) -> None:
    response = admin_client.post(
        reverse("dynamic-user-admin-user-list"),
        {
            "username": "newstaff",
            "email": "newstaff@example.com",
            "password": "pw",
            "is_staff": True,
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["is_staff"] is True


def test_non_staff_cannot_create_a_user(client: APIClient) -> None:
    response = client.post(
        reverse("dynamic-user-admin-user-list"),
        {"username": "x", "email": "x@example.com"},
        format="json",
    )
    appkit_assert_error_envelope(response, code="permission_denied", status=403)


def test_created_user_gets_profile_and_setting(staff_client: APIClient) -> None:
    response = staff_client.post(
        reverse("dynamic-user-admin-user-list"),
        {"username": "provisioned", "email": "provisioned@example.com"},
        format="json",
    )
    assert response.status_code == 201
    user_id = response.data["id"]
    assert get_profile_model().objects.filter(user_id=user_id).exists()
    assert get_setting_model().objects.filter(user_id=user_id).exists()


# ------------------------------------------------------------------------------- DELETE /{id}/


def test_staff_admin_cannot_delete_a_user(staff_client: APIClient, other_user: Any) -> None:
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = staff_client.delete(url)
    appkit_assert_error_envelope(response, code="permission_denied", status=403)
    other_user.refresh_from_db()  # still exists


def test_superuser_can_delete_a_user(admin_client: APIClient, other_user: Any) -> None:
    from django.contrib.auth import get_user_model

    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = admin_client.delete(url)
    assert response.status_code == 204
    assert not get_user_model().objects.filter(pk=other_user.pk).exists()


def test_delete_user_still_403s_a_staff_admin_under_admin_requires_superuser_true(
    staff_client: APIClient, other_user: Any
) -> None:
    with override_settings(DYNAMIC_USER={"ADMIN_REQUIRES_SUPERUSER": True}):
        url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
        response = staff_client.delete(url)
    assert response.status_code == 403


def test_anonymous_cannot_delete_a_user(appkit_api_client: APIClient, other_user: Any) -> None:
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = appkit_api_client.delete(url)
    appkit_assert_error_envelope(response, code="not_authenticated", status=403)


# ------------------------------------------------------------------------ POST /{id}/set-password/


def test_staff_admin_cannot_set_a_password(staff_client: APIClient, other_user: Any) -> None:
    url = reverse("dynamic-user-admin-user-set-password", kwargs={"id": other_user.pk})
    response = staff_client.post(url, {"password": "brandnewpassword123"}, format="json")
    appkit_assert_error_envelope(response, code="permission_denied", status=403)


def test_superuser_can_set_a_password(admin_client: APIClient, other_user: Any) -> None:
    url = reverse("dynamic-user-admin-user-set-password", kwargs={"id": other_user.pk})
    response = admin_client.post(url, {"password": "brandnewpassword123"}, format="json")
    assert response.status_code == 204
    other_user.refresh_from_db()
    assert other_user.check_password("brandnewpassword123")


def test_set_password_runs_auth_password_validators(
    admin_client: APIClient, other_user: Any
) -> None:
    """tests/backend/settings.py sets no AUTH_PASSWORD_VALIDATORS at all (this app defines no
    opinionated password policy of its own) — override it here to prove validate_password is
    genuinely called, not skipped."""
    validators = [
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
            "OPTIONS": {"min_length": 8},
        }
    ]
    with override_settings(AUTH_PASSWORD_VALIDATORS=validators):
        url = reverse("dynamic-user-admin-user-set-password", kwargs={"id": other_user.pk})
        response = admin_client.post(url, {"password": "123"}, format="json")
    assert response.status_code == 400


def test_set_password_fires_user_password_set(admin_client: APIClient, other_user: Any) -> None:
    from dynamic_user import signals

    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.user_password_set.connect(_receiver)
    try:
        url = reverse("dynamic-user-admin-user-set-password", kwargs={"id": other_user.pk})
        admin_client.post(url, {"password": "brandnewpassword123"}, format="json")
    finally:
        signals.user_password_set.disconnect(_receiver)

    assert len(received) == 1
    assert received[0]["user_id"] == other_user.pk


# ------------------------------------------------------------------------------- /profiles/


def test_staff_admin_can_list_profiles(staff_client: APIClient, other_profile: Any) -> None:
    response = staff_client.get(reverse("dynamic-user-admin-profile-list"))
    assert response.status_code == 200
    pks = {row["id"] for row in response.data["results"]}
    assert other_profile.pk in pks


def test_admin_profile_list_includes_private_profiles(
    staff_client: APIClient, other_profile: Any
) -> None:
    """Unlike self-service GET /profiles/, the admin collection is not restricted to
    is_public=True."""
    other_profile.is_public = False
    other_profile.save(update_fields=["is_public"])
    response = staff_client.get(reverse("dynamic-user-admin-profile-list"))
    pks = {row["id"] for row in response.data["results"]}
    assert other_profile.pk in pks


def test_non_staff_cannot_list_profiles(client: APIClient) -> None:
    response = client.get(reverse("dynamic-user-admin-profile-list"))
    appkit_assert_error_envelope(response, code="permission_denied", status=403)


def test_staff_admin_can_create_a_profile_for_a_user_with_none(
    staff_client: APIClient, other_user: Any
) -> None:
    get_profile_model().objects.filter(user=other_user).delete()
    response = staff_client.post(
        reverse("dynamic-user-admin-profile-list"),
        {"user": other_user.pk, "bio": "hello"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["bio"] == "hello"


def test_create_profile_rejects_a_duplicate_user(
    staff_client: APIClient, other_profile: Any
) -> None:
    response = staff_client.post(
        reverse("dynamic-user-admin-profile-list"),
        {"user": other_profile.user_id, "bio": "dup"},
        format="json",
    )
    assert response.status_code == 400


def test_admin_profile_detail_get_by_profile_pk(
    staff_client: APIClient, other_profile: Any
) -> None:
    url = reverse("dynamic-user-admin-profile-detail", kwargs={"profile_id": other_profile.pk})
    response = staff_client.get(url)
    assert response.status_code == 200
    assert response.data["id"] == other_profile.pk


def test_admin_profile_detail_patch_updates_via_service(
    staff_client: APIClient, other_profile: Any
) -> None:
    url = reverse("dynamic-user-admin-profile-detail", kwargs={"profile_id": other_profile.pk})
    response = staff_client.patch(url, {"bio": "updated"}, format="json")
    assert response.status_code == 200
    other_profile.refresh_from_db()
    assert other_profile.bio == "updated"


def test_admin_profile_detail_delete(staff_client: APIClient, other_profile: Any) -> None:
    profile_id = other_profile.pk
    url = reverse("dynamic-user-admin-profile-detail", kwargs={"profile_id": profile_id})
    response = staff_client.delete(url)
    assert response.status_code == 204
    assert not get_profile_model().objects.filter(pk=profile_id).exists()


# ------------------------------------------------------------------------------- /settings/


def test_staff_admin_can_list_settings(staff_client: APIClient, other_user: Any) -> None:
    setting_model = get_setting_model()
    setting, _ = setting_model.objects.get_or_create(user=other_user)
    response = staff_client.get(reverse("dynamic-user-admin-setting-list"))
    assert response.status_code == 200
    pks = {row["id"] for row in response.data["results"]}
    assert setting.pk in pks


def test_staff_admin_can_create_a_setting_for_a_user_with_none(
    staff_client: APIClient, other_user: Any
) -> None:
    get_setting_model().objects.filter(user=other_user).delete()
    response = staff_client.post(
        reverse("dynamic-user-admin-setting-list"),
        {"user": other_user.pk, "language": "fa"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["language"] == "fa"


def test_admin_setting_detail_get_patch_delete_by_setting_pk(
    staff_client: APIClient, other_user: Any
) -> None:
    setting_model = get_setting_model()
    setting, _ = setting_model.objects.get_or_create(user=other_user)

    get_url = reverse("dynamic-user-admin-setting-detail", kwargs={"setting_id": setting.pk})
    assert staff_client.get(get_url).status_code == 200

    patch_response = staff_client.patch(get_url, {"language": "fa"}, format="json")
    assert patch_response.status_code == 200
    setting.refresh_from_db()
    assert setting.language == "fa"

    delete_response = staff_client.delete(get_url)
    assert delete_response.status_code == 204
    assert not setting_model.objects.filter(pk=setting.pk).exists()


# --------------------------------------------------------------------------- /deletion-requests/


def test_admin_deletion_request_detail_get_by_id(
    staff_client: APIClient, pending_deletion_request: AccountDeletionRequest
) -> None:
    url = reverse(
        "dynamic-user-admin-deletion-request-detail",
        kwargs={"id": pending_deletion_request.pk},
    )
    response = staff_client.get(url)
    assert response.status_code == 200
    assert response.data["id"] == pending_deletion_request.pk


def test_admin_can_create_a_deletion_request_for_a_user(
    staff_client: APIClient, other_user: Any
) -> None:
    response = staff_client.post(
        reverse("dynamic-user-admin-deletion-request-list"),
        {"user": other_user.pk, "reason": "admin-filed"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["user"] == other_user.pk


def test_admin_create_deletion_request_rejects_a_duplicate(
    staff_client: APIClient, pending_deletion_request: AccountDeletionRequest
) -> None:
    response = staff_client.post(
        reverse("dynamic-user-admin-deletion-request-list"),
        {"user": pending_deletion_request.user_id},
        format="json",
    )
    assert response.status_code == 409


def test_admin_can_cancel_a_pending_deletion_request(
    staff_client: APIClient, pending_deletion_request: AccountDeletionRequest
) -> None:
    request_id = pending_deletion_request.pk
    url = reverse("dynamic-user-admin-deletion-request-detail", kwargs={"id": request_id})
    response = staff_client.delete(url)
    assert response.status_code == 204
    assert not AccountDeletionRequest.objects.filter(pk=request_id).exists()


def test_admin_can_cancel_an_approved_deletion_request(
    staff_client: APIClient, approved_deletion_request: AccountDeletionRequest
) -> None:
    """Unlike the self-service DeletionService.cancel (PENDING only), the admin cancel accepts
    APPROVED too — an admin reasonably wants to withdraw a request they already approved."""
    request_id = approved_deletion_request.pk
    url = reverse("dynamic-user-admin-deletion-request-detail", kwargs={"id": request_id})
    response = staff_client.delete(url)
    assert response.status_code == 204
    assert not AccountDeletionRequest.objects.filter(pk=request_id).exists()


def test_admin_cancel_on_a_rejected_request_returns_409(staff_client: APIClient, user: Any) -> None:
    rejected = AccountDeletionRequest.objects.create(
        user=user, status=AccountDeletionRequest.Status.REJECTED
    )
    url = reverse("dynamic-user-admin-deletion-request-detail", kwargs={"id": rejected.pk})
    response = staff_client.delete(url)
    assert response.status_code == 409


# ------------------------------------------------------------------------------- /change-log/


def test_staff_admin_can_list_change_log(staff_client: APIClient, user: Any) -> None:
    from django.contrib.contenttypes.models import ContentType

    entry = ChangeLogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(user),
        object_id=user.pk,
        field_name="name",
        old_value="",
        new_value="Alice",
    )
    response = staff_client.get(reverse("dynamic-user-admin-change-log-list"))
    assert response.status_code == 200
    pks = {row["id"] for row in response.data["results"]}
    assert entry.pk in pks


def test_change_log_detail_get(staff_client: APIClient, user: Any) -> None:
    from django.contrib.contenttypes.models import ContentType

    entry = ChangeLogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(user),
        object_id=user.pk,
        field_name="name",
    )
    url = reverse("dynamic-user-admin-change-log-detail", kwargs={"id": entry.pk})
    response = staff_client.get(url)
    assert response.status_code == 200


def test_staff_admin_cannot_delete_a_change_log_entry(staff_client: APIClient, user: Any) -> None:
    from django.contrib.contenttypes.models import ContentType

    entry = ChangeLogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(user),
        object_id=user.pk,
        field_name="name",
    )
    url = reverse("dynamic-user-admin-change-log-detail", kwargs={"id": entry.pk})
    response = staff_client.delete(url)
    appkit_assert_error_envelope(response, code="permission_denied", status=403)
    assert ChangeLogEntry.objects.filter(pk=entry.pk).exists()


def test_superuser_can_delete_a_change_log_entry(admin_client: APIClient, user: Any) -> None:
    from django.contrib.contenttypes.models import ContentType

    entry = ChangeLogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(user),
        object_id=user.pk,
        field_name="name",
    )
    url = reverse("dynamic-user-admin-change-log-detail", kwargs={"id": entry.pk})
    response = admin_client.delete(url)
    assert response.status_code == 204
    assert not ChangeLogEntry.objects.filter(pk=entry.pk).exists()


# ------------------------------------------------------------------------------- /log-entries/


def test_staff_admin_can_list_log_entries(staff_client: APIClient, admin_user: Any) -> None:
    from django.contrib.admin.models import ADDITION

    LogEntry.objects.log_actions(
        admin_user.pk,
        [admin_user],
        ADDITION,
        change_message="created",
        single_object=True,
    )
    response = staff_client.get(reverse("dynamic-user-admin-log-entry-list"))
    assert response.status_code == 200
    assert response.data["count"] >= 1


def test_log_entry_detail_get(staff_client: APIClient, admin_user: Any) -> None:
    from django.contrib.admin.models import ADDITION

    entry = LogEntry.objects.log_actions(
        admin_user.pk, [admin_user], ADDITION, change_message="x", single_object=True
    )
    log_entry = entry[0] if isinstance(entry, list) else entry
    url = reverse("dynamic-user-admin-log-entry-detail", kwargs={"id": log_entry.pk})
    response = staff_client.get(url)
    assert response.status_code == 200


def test_staff_admin_cannot_delete_a_log_entry(staff_client: APIClient, admin_user: Any) -> None:
    from django.contrib.admin.models import ADDITION

    entry = LogEntry.objects.log_actions(
        admin_user.pk, [admin_user], ADDITION, change_message="x", single_object=True
    )
    log_entry = entry[0] if isinstance(entry, list) else entry
    url = reverse("dynamic-user-admin-log-entry-detail", kwargs={"id": log_entry.pk})
    response = staff_client.delete(url)
    appkit_assert_error_envelope(response, code="permission_denied", status=403)


def test_superuser_can_delete_a_log_entry(admin_client: APIClient, admin_user: Any) -> None:
    from django.contrib.admin.models import ADDITION

    entry = LogEntry.objects.log_actions(
        admin_user.pk, [admin_user], ADDITION, change_message="x", single_object=True
    )
    log_entry = entry[0] if isinstance(entry, list) else entry
    url = reverse("dynamic-user-admin-log-entry-detail", kwargs={"id": log_entry.pk})
    response = admin_client.delete(url)
    assert response.status_code == 204


def test_admin_api_write_creates_a_log_entry(staff_client: APIClient, other_user: Any) -> None:
    """The v1.1.0 audit-trail addition: an admin-API PATCH now produces a LogEntry, matching
    what Django Admin itself already auto-logs for the equivalent change-form save."""
    before = LogEntry.objects.count()
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = staff_client.patch(url, {"name": "Renamed"}, format="json")
    assert response.status_code == 200
    assert LogEntry.objects.count() == before + 1


# ------------------------------------------------------------------------ /groups/, /permissions/


def test_staff_admin_can_list_groups(staff_client: APIClient) -> None:
    Group.objects.create(name="editors")
    response = staff_client.get(reverse("dynamic-user-admin-group-list"))
    assert response.status_code == 200
    names = {row["name"] for row in response.data["results"]}
    assert "editors" in names


def test_group_detail_get(staff_client: APIClient) -> None:
    group = Group.objects.create(name="viewers")
    url = reverse("dynamic-user-admin-group-detail", kwargs={"id": group.pk})
    response = staff_client.get(url)
    assert response.status_code == 200
    assert response.data["name"] == "viewers"


def test_staff_admin_can_list_permissions(staff_client: APIClient) -> None:
    response = staff_client.get(reverse("dynamic-user-admin-permission-list"))
    assert response.status_code == 200
    assert response.data["count"] > 0
    # A real Permission's shape — proves this isn't an empty/stub queryset.
    assert Permission.objects.count() == response.data["count"]


def test_non_staff_cannot_list_groups_or_permissions(client: APIClient) -> None:
    assert client.get(reverse("dynamic-user-admin-group-list")).status_code == 403
    assert client.get(reverse("dynamic-user-admin-permission-list")).status_code == 403
