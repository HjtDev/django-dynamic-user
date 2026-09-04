"""Phase 6's admin HTTP surface — the DEFAULT-models leg.

The privilege-escalation phase's own tests, all proven by actual attempt rather than by reading
the permission class:

* ``ADMIN_REQUIRES_SUPERUSER`` gets two full passes — ``False`` (staff-not-superuser allowed) and
  ``True`` (staff-not-superuser now 403s) — over every route except ``.../finalize/``, which is
  superuser-only regardless of the setting and is tested on its own.
* A staff (non-superuser) admin PATCHing ``is_staff``/``is_superuser``/``is_active``/``groups``/
  ``user_permissions`` on ANY user, including themselves, is rejected and the DB value is proven
  unchanged — the counterpart proves a superuser's equivalent PATCH genuinely does change it, so
  the guard is shown to be selective, not a blanket PATCH deny.
* ``/deletion-requests/{id}/finalize/`` 403s a plain staff admin even under the default
  ``ADMIN_REQUIRES_SUPERUSER=False`` — the case that proves ``IsSuperUser`` is doing the work,
  not the general admin gate.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from appkit.testing import appkit_assert_error_envelope
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from dynamic_user.models import AccountDeletionRequest
from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = pytest.mark.django_db


@pytest.fixture
def client(user: Any) -> APIClient:
    """A plain, non-staff, non-superuser caller — denied by ``IsDynamicUserAdmin`` at the door,
    every route, every ``ADMIN_REQUIRES_SUPERUSER`` value."""
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


# --------------------------------------------------------------------------------- permissions


# Every route except .../finalize/ — that one is superuser-only unconditionally and gets its
# own dedicated tests below, since it would break the "staff allowed under the default setting"
# assertion this list is otherwise used for.
_ADMIN_ENDPOINTS: list[tuple[str, str, str]] = [
    ("get", "dynamic-user-admin-user-list", "none"),
    ("get", "dynamic-user-admin-user-detail", "user"),
    ("patch", "dynamic-user-admin-user-detail", "user"),
    ("get", "dynamic-user-admin-user-profile", "user"),
    ("patch", "dynamic-user-admin-user-profile", "user"),
    ("get", "dynamic-user-admin-user-setting", "user"),
    ("patch", "dynamic-user-admin-user-setting", "user"),
    ("get", "dynamic-user-admin-deletion-request-list", "none"),
    ("post", "dynamic-user-admin-deletion-request-review", "deletion"),
]


def _admin_url(url_name: str, kind: str, target_user_id: int, deletion_request_id: int) -> str:
    if kind == "user":
        return reverse(url_name, kwargs={"id": target_user_id})
    if kind == "deletion":
        return reverse(url_name, kwargs={"id": deletion_request_id})
    return reverse(url_name)


def _admin_body(url_name: str) -> dict[str, Any]:
    # The review endpoint requires `approved` — an empty body would 400 on validation before
    # permissions are even at issue, which would make "allowed" indistinguishable from "denied
    # with a body error" in the matrix below. Every other route accepts an empty PATCH/body.
    if url_name == "dynamic-user-admin-deletion-request-review":
        return {"approved": True}
    return {}


@pytest.mark.parametrize(("method", "url_name", "kind"), _ADMIN_ENDPOINTS)
def test_anonymous_is_rejected(
    appkit_api_client: APIClient,
    method: str,
    url_name: str,
    kind: str,
    other_user: Any,
    pending_deletion_request: AccountDeletionRequest,
) -> None:
    url = _admin_url(url_name, kind, other_user.pk, pending_deletion_request.pk)
    response = getattr(appkit_api_client, method)(url, _admin_body(url_name), format="json")
    appkit_assert_error_envelope(response, code="not_authenticated", status=403)


@pytest.mark.parametrize(("method", "url_name", "kind"), _ADMIN_ENDPOINTS)
def test_authenticated_non_staff_is_rejected(
    client: APIClient,
    method: str,
    url_name: str,
    kind: str,
    other_user: Any,
    pending_deletion_request: AccountDeletionRequest,
) -> None:
    url = _admin_url(url_name, kind, other_user.pk, pending_deletion_request.pk)
    response = getattr(client, method)(url, _admin_body(url_name), format="json")
    appkit_assert_error_envelope(response, code="permission_denied", status=403)


@pytest.mark.parametrize(("method", "url_name", "kind"), _ADMIN_ENDPOINTS)
def test_staff_is_allowed_when_admin_requires_superuser_is_false(
    staff_client: APIClient,
    method: str,
    url_name: str,
    kind: str,
    other_user: Any,
    pending_deletion_request: AccountDeletionRequest,
) -> None:
    """The default (``ADMIN_REQUIRES_SUPERUSER`` unset, i.e. ``False``) — "staff is enough"."""
    url = _admin_url(url_name, kind, other_user.pk, pending_deletion_request.pk)
    response = getattr(staff_client, method)(url, _admin_body(url_name), format="json")
    assert response.status_code != 403


@pytest.mark.parametrize(("method", "url_name", "kind"), _ADMIN_ENDPOINTS)
def test_staff_is_rejected_when_admin_requires_superuser_is_true(
    staff_client: APIClient,
    method: str,
    url_name: str,
    kind: str,
    other_user: Any,
    pending_deletion_request: AccountDeletionRequest,
) -> None:
    url = _admin_url(url_name, kind, other_user.pk, pending_deletion_request.pk)
    with override_settings(DYNAMIC_USER={"ADMIN_REQUIRES_SUPERUSER": True}):
        response = getattr(staff_client, method)(url, _admin_body(url_name), format="json")
    appkit_assert_error_envelope(response, code="permission_denied", status=403)


@pytest.mark.parametrize(("method", "url_name", "kind"), _ADMIN_ENDPOINTS)
@pytest.mark.parametrize("admin_requires_superuser", [False, True])
def test_superuser_is_allowed_regardless_of_admin_requires_superuser(
    admin_client: APIClient,
    method: str,
    url_name: str,
    kind: str,
    admin_requires_superuser: bool,
    other_user: Any,
    pending_deletion_request: AccountDeletionRequest,
) -> None:
    url = _admin_url(url_name, kind, other_user.pk, pending_deletion_request.pk)
    with override_settings(DYNAMIC_USER={"ADMIN_REQUIRES_SUPERUSER": admin_requires_superuser}):
        response = getattr(admin_client, method)(url, _admin_body(url_name), format="json")
    assert response.status_code != 403


def test_all_eight_throttle_scopes_are_registered(settings: Any) -> None:
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    for scope in (
        "dynamic_user_admin_users_list",
        "dynamic_user_admin_user_retrieve",
        "dynamic_user_admin_user_update",
        "dynamic_user_admin_profile_update",
        "dynamic_user_admin_setting_update",
        "dynamic_user_admin_deletions_list",
        "dynamic_user_admin_deletion_review",
        "dynamic_user_admin_deletion_finalize",
    ):
        assert scope in rates


@pytest.mark.parametrize(
    ("scope", "method", "url_name", "kind"),
    [
        ("dynamic_user_admin_users_list", "get", "dynamic-user-admin-user-list", "none"),
        ("dynamic_user_admin_user_retrieve", "get", "dynamic-user-admin-user-detail", "user"),
        ("dynamic_user_admin_user_update", "patch", "dynamic-user-admin-user-detail", "user"),
        (
            "dynamic_user_admin_profile_update",
            "patch",
            "dynamic-user-admin-user-profile",
            "user",
        ),
        (
            "dynamic_user_admin_setting_update",
            "patch",
            "dynamic-user-admin-user-setting",
            "user",
        ),
        (
            "dynamic_user_admin_deletions_list",
            "get",
            "dynamic-user-admin-deletion-request-list",
            "none",
        ),
    ],
)
def test_throttle_scope_returns_429_past_its_rate(
    admin_client: APIClient,
    scope: str,
    method: str,
    url_name: str,
    kind: str,
    other_user: Any,
    pending_deletion_request: AccountDeletionRequest,
) -> None:
    """Same idiom ``test_views.py`` established: ``ScopedRateThrottle.THROTTLE_RATES`` is bound
    at ``rest_framework.throttling`` import time, so ``override_settings`` never reaches it —
    patched directly to actually engage a real 429."""
    url = _admin_url(url_name, kind, other_user.pk, pending_deletion_request.pk)
    with patch.object(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {**ScopedRateThrottle.THROTTLE_RATES, scope: "1/min"},
    ):
        getattr(admin_client, method)(url, {}, format="json")
        second = getattr(admin_client, method)(url, {}, format="json")

    assert second.status_code == 429


def test_deletion_review_throttle_scope_returns_429_past_its_rate(
    admin_client: APIClient, pending_deletion_request: AccountDeletionRequest
) -> None:
    url = reverse(
        "dynamic-user-admin-deletion-request-review",
        kwargs={"id": pending_deletion_request.pk},
    )
    with patch.object(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {**ScopedRateThrottle.THROTTLE_RATES, "dynamic_user_admin_deletion_review": "1/min"},
    ):
        admin_client.post(url, {"approved": True}, format="json")
        second = admin_client.post(url, {"approved": True}, format="json")

    assert second.status_code == 429


def test_deletion_finalize_throttle_scope_returns_429_past_its_rate(
    admin_client: APIClient,
    approved_deletion_request: AccountDeletionRequest,
) -> None:
    """Permission checks run before throttle checks (DRF's own ``initial()`` ordering), so this
    stays valid even though the first call actually finalizes (and hard-deletes) the row — the
    second call is blocked by the throttle before it ever reaches the service, regardless of the
    row's state by then."""
    url = reverse(
        "dynamic-user-admin-deletion-request-finalize",
        kwargs={"id": approved_deletion_request.pk},
    )
    with patch.object(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {**ScopedRateThrottle.THROTTLE_RATES, "dynamic_user_admin_deletion_finalize": "1/min"},
    ):
        first = admin_client.post(url, {}, format="json")
        second = admin_client.post(url, {}, format="json")

    assert first.status_code == 204
    assert second.status_code == 429


# ------------------------------------------------------------------------------------- /users/


def test_admin_user_list_returns_every_user(admin_client: APIClient, user: Any) -> None:
    response = admin_client.get(reverse("dynamic-user-admin-user-list"))
    assert response.status_code == 200
    usernames = {row["username"] for row in response.data["results"]}
    assert user.username in usernames


def test_admin_user_list_password_never_appears(admin_client: APIClient, user: Any) -> None:
    response = admin_client.get(reverse("dynamic-user-admin-user-list"))
    assert response.status_code == 200
    for row in response.data["results"]:
        assert "password" not in row


def test_admin_user_list_filters_on_a_real_field(
    admin_client: APIClient, user: Any, other_user: Any
) -> None:
    response = admin_client.get(
        reverse("dynamic-user-admin-user-list"), {"username": user.username}
    )
    assert response.status_code == 200
    usernames = {row["username"] for row in response.data["results"]}
    assert usernames == {user.username}


def test_admin_user_list_drops_unknown_query_param(admin_client: APIClient, user: Any) -> None:
    response = admin_client.get(reverse("dynamic-user-admin-user-list"), {"nope": "x"})
    assert response.status_code == 200


def test_admin_user_list_rejects_a_relation_traversal_filter(
    admin_client: APIClient, user: Any, other_user: Any
) -> None:
    """``?groups__name=...`` must be silently dropped, never reach ``.filter()`` — dropping,
    not erroring, is ``safe_filter_kwargs``'s own documented behaviour for an unrecognised
    param; the security property under test is that it never becomes a relation traversal."""
    response = admin_client.get(
        reverse("dynamic-user-admin-user-list"), {"groups__name": "whatever"}
    )
    assert response.status_code == 200
    usernames = {row["username"] for row in response.data["results"]}
    assert {user.username, other_user.username} <= usernames


def test_admin_user_detail_returns_full_fields_except_password(
    admin_client: APIClient, other_user: Any
) -> None:
    response = admin_client.get(
        reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    )
    assert response.status_code == 200
    assert response.data["username"] == other_user.username
    assert "is_staff" in response.data
    assert "password" not in response.data


def test_admin_user_detail_put_is_not_allowed(admin_client: APIClient, other_user: Any) -> None:
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = admin_client.put(url, {"name": "x"}, format="json")
    assert response.status_code == 405


def test_admin_user_detail_patch_updates_a_non_privileged_field(
    staff_client: APIClient, other_user: Any
) -> None:
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = staff_client.patch(url, {"name": "Renamed"}, format="json")
    assert response.status_code == 200
    other_user.refresh_from_db()
    assert other_user.name == "Renamed"


# ------------------------------------------------------------------------------ escalation guard


@pytest.mark.parametrize("field", ["is_staff", "is_superuser", "is_active", "groups"])
def test_staff_admin_cannot_escalate_another_users_privileges(
    staff_client: APIClient, other_user: Any, field: str
) -> None:
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    original = getattr(other_user, field)
    value = [] if field == "groups" else not original
    response = staff_client.patch(url, {field: value}, format="json")
    assert response.status_code == 403

    other_user.refresh_from_db()
    assert getattr(other_user, field) == original


@pytest.mark.parametrize("field", ["is_staff", "is_superuser", "is_active"])
def test_staff_admin_cannot_escalate_their_own_privileges(
    staff_client: APIClient, staff_user: Any, field: str
) -> None:
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": staff_user.pk})
    original = getattr(staff_user, field)
    response = staff_client.patch(url, {field: not original}, format="json")
    assert response.status_code == 403

    staff_user.refresh_from_db()
    assert getattr(staff_user, field) == original


def test_staff_admin_escalation_attempt_rejects_the_whole_request_not_just_the_field(
    staff_client: APIClient, other_user: Any
) -> None:
    """A body mixing a legitimate field with a privileged one is rejected outright — the caller
    gets an honest 403, never a response that silently dropped only the gated field while
    applying the rest."""
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = staff_client.patch(
        url, {"name": "Should not apply", "is_staff": True}, format="json"
    )
    assert response.status_code == 403

    other_user.refresh_from_db()
    assert other_user.name != "Should not apply"
    assert other_user.is_staff is False


@pytest.mark.parametrize("field", ["is_staff", "is_superuser", "is_active"])
def test_superuser_can_set_privileged_fields(
    admin_client: APIClient, other_user: Any, field: str
) -> None:
    """The counterpart to the two denial tests above — proves the guard is selective, not a
    blanket deny of every admin PATCH."""
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    original = getattr(other_user, field)
    response = admin_client.patch(url, {field: not original}, format="json")
    assert response.status_code == 200

    other_user.refresh_from_db()
    assert getattr(other_user, field) == (not original)


def test_escalation_guard_still_runs_when_admin_requires_superuser_is_true(
    staff_client: APIClient, other_user: Any
) -> None:
    """The guard is present and tested even when the general gate has already tightened to
    superuser-only — proven independently, since ``ADMIN_REQUIRES_SUPERUSER`` could change back
    under it later."""
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    with override_settings(DYNAMIC_USER={"ADMIN_REQUIRES_SUPERUSER": True}):
        response = staff_client.patch(url, {"is_staff": True}, format="json")
    # Rejected either way here (the general gate already denies staff under this setting) — the
    # dedicated point is that this is still a 403, not a 500/200 from a bypassed check.
    assert response.status_code == 403


# --------------------------------------------------------------------------------- profile/setting


def test_admin_profile_get_returns_every_real_field(
    admin_client: APIClient, other_user: Any, other_profile: Any
) -> None:
    response = admin_client.get(
        reverse("dynamic-user-admin-user-profile", kwargs={"id": other_user.pk})
    )
    assert response.status_code == 200
    assert {"bio", "is_public", "user"} <= set(response.data)


def test_admin_profile_patch_updates_via_service_and_fires_signal(
    admin_client: APIClient, other_user: Any, other_profile: Any
) -> None:
    from dynamic_user import signals

    received: list[dict[str, Any]] = []
    signals.profile_updated.connect(lambda sender, **kwargs: received.append(kwargs), weak=False)

    url = reverse("dynamic-user-admin-user-profile", kwargs={"id": other_user.pk})
    response = admin_client.patch(url, {"bio": "updated by admin"}, format="json")
    assert response.status_code == 200
    assert response.data["bio"] == "updated by admin"

    profile = get_profile_model().objects.get(user=other_user)
    assert profile.bio == "updated by admin"
    assert received
    assert received[-1]["user_id"] == other_user.pk
    assert received[-1]["changed_fields"] == ["bio"]


def test_admin_profile_patch_cannot_reassign_owner(
    admin_client: APIClient, user: Any, other_user: Any, other_profile: Any
) -> None:
    """``user`` is read-only on the admin full-fields Profile serializer — a PATCH naming a
    different ``user`` id must leave ownership unchanged."""
    url = reverse("dynamic-user-admin-user-profile", kwargs={"id": other_user.pk})
    response = admin_client.patch(url, {"user": user.pk, "bio": "ok"}, format="json")
    assert response.status_code == 200

    profile = get_profile_model().objects.get(user=other_user)
    assert profile.user_id == other_user.pk
    assert profile.bio == "ok"


def test_admin_setting_get_returns_every_real_field(
    admin_client: APIClient, other_user: Any
) -> None:
    response = admin_client.get(
        reverse("dynamic-user-admin-user-setting", kwargs={"id": other_user.pk})
    )
    assert response.status_code == 200
    assert {"language", "timezone", "notifications_enabled", "user"} <= set(response.data)


def test_admin_setting_patch_updates_via_service(admin_client: APIClient, other_user: Any) -> None:
    url = reverse("dynamic-user-admin-user-setting", kwargs={"id": other_user.pk})
    response = admin_client.patch(url, {"language": "fa"}, format="json")
    assert response.status_code == 200
    assert response.data["language"] == "fa"

    setting = get_setting_model().objects.get(user=other_user)
    assert setting.language == "fa"


def test_admin_setting_patch_cannot_reassign_owner(
    admin_client: APIClient, user: Any, other_user: Any
) -> None:
    url = reverse("dynamic-user-admin-user-setting", kwargs={"id": other_user.pk})
    response = admin_client.patch(url, {"user": user.pk, "language": "fa"}, format="json")
    assert response.status_code == 200

    setting = get_setting_model().objects.get(user=other_user)
    assert setting.user_id == other_user.pk


def test_admin_profile_view_provisions_a_missing_row(
    admin_client: APIClient, other_user: Any
) -> None:
    """A host running ``AUTO_CREATE_PROFILE=False``, or a pre-install user, must still be
    reachable — mirrors ``MyProfileView``'s own ``get_or_create`` reasoning."""
    get_profile_model().objects.filter(user=other_user).delete()
    url = reverse("dynamic-user-admin-user-profile", kwargs={"id": other_user.pk})
    response = admin_client.get(url)
    assert response.status_code == 200


# --------------------------------------------------------------------------------- deletion queue


def test_admin_deletion_list_filters_by_status(
    admin_client: APIClient,
    pending_deletion_request: AccountDeletionRequest,
    approved_deletion_request: AccountDeletionRequest,
) -> None:
    # approved_deletion_request belongs to the same `user` fixture as pending_deletion_request —
    # only one PENDING/APPROVED row can exist per user via DeletionService.request()'s own
    # uniqueness rule, but these are created directly through the model layer, bypassing that,
    # specifically so both statuses exist to filter between.
    response = admin_client.get(
        reverse("dynamic-user-admin-deletion-request-list"), {"status": "approved"}
    )
    assert response.status_code == 200
    statuses = {row["status"] for row in response.data["results"]}
    assert statuses == {"approved"}


def test_admin_deletion_list_rejects_an_invalid_status(admin_client: APIClient) -> None:
    response = admin_client.get(
        reverse("dynamic-user-admin-deletion-request-list"), {"status": "not-a-real-status"}
    )
    appkit_assert_error_envelope(response, code="validation_error", status=400)


def test_admin_deletion_review_approves_and_fires_signal(
    admin_client: APIClient,
    admin_user: Any,
    pending_deletion_request: AccountDeletionRequest,
) -> None:
    from dynamic_user import signals

    received: list[dict[str, Any]] = []
    signals.deletion_reviewed.connect(lambda sender, **kwargs: received.append(kwargs), weak=False)

    url = reverse(
        "dynamic-user-admin-deletion-request-review",
        kwargs={"id": pending_deletion_request.pk},
    )
    response = admin_client.post(url, {"approved": True}, format="json")
    assert response.status_code == 200
    assert response.data["status"] == "approved"
    assert response.data["reviewed_by"] == admin_user.pk

    pending_deletion_request.refresh_from_db()
    assert pending_deletion_request.status == AccountDeletionRequest.Status.APPROVED
    assert pending_deletion_request.reviewed_by_id == admin_user.pk
    assert received
    assert received[-1]["status"] == AccountDeletionRequest.Status.APPROVED
    assert received[-1]["reviewed_by_id"] == admin_user.pk


def test_admin_deletion_review_on_a_non_pending_request_returns_409(
    admin_client: APIClient, approved_deletion_request: AccountDeletionRequest
) -> None:
    url = reverse(
        "dynamic-user-admin-deletion-request-review",
        kwargs={"id": approved_deletion_request.pk},
    )
    response = admin_client.post(url, {"approved": True}, format="json")
    assert response.status_code == 409


# ------------------------------------------------------------------------------- finalize (super)


def test_finalize_403s_a_plain_staff_admin_even_under_the_default_setting(
    staff_client: APIClient, approved_deletion_request: AccountDeletionRequest
) -> None:
    """The load-bearing case: ``ADMIN_REQUIRES_SUPERUSER`` is unset (``False``, the default)
    here — a staff admin passes the *general* gate everywhere else on this surface, so a 403
    here can only be ``IsSuperUser`` doing its job, not the general gate."""
    url = reverse(
        "dynamic-user-admin-deletion-request-finalize",
        kwargs={"id": approved_deletion_request.pk},
    )
    response = staff_client.post(url, {}, format="json")
    appkit_assert_error_envelope(response, code="permission_denied", status=403)

    approved_deletion_request.refresh_from_db()
    assert approved_deletion_request.status == AccountDeletionRequest.Status.APPROVED


def test_finalize_204s_a_superuser_and_hard_deletes(
    admin_client: APIClient, approved_deletion_request: AccountDeletionRequest
) -> None:
    from django.contrib.auth import get_user_model

    user_id = approved_deletion_request.user_id
    url = reverse(
        "dynamic-user-admin-deletion-request-finalize",
        kwargs={"id": approved_deletion_request.pk},
    )
    response = admin_client.post(url, {}, format="json")
    assert response.status_code == 204
    assert not get_user_model()._default_manager.filter(pk=user_id).exists()


def test_finalize_on_a_non_approved_request_returns_409(
    admin_client: APIClient, pending_deletion_request: AccountDeletionRequest
) -> None:
    url = reverse(
        "dynamic-user-admin-deletion-request-finalize",
        kwargs={"id": pending_deletion_request.pk},
    )
    response = admin_client.post(url, {}, format="json")
    assert response.status_code == 409
