"""Phase 5's self-service HTTP surface — the DEFAULT-models leg.

Every permission-gated route is proven, not assumed: an unauthenticated request against every
route in ``_ENDPOINTS`` asserts the exact ``error.code``/status DRF actually produces under this
app's chosen (unmodified) ``DEFAULT_AUTHENTICATION_CLASSES`` (``tests/backend/settings.py``'s own
docstring explains why that's 403/``not_authenticated``, not 401). The private-profile case
asserts the exact status code (404, not merely "not 200") — swapping ``IsPublicOrOwner`` for a
permission that only checks authentication must make that one test fail, which is this phase's
own verification requirement.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from appkit.testing import appkit_assert_error_envelope
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from dynamic_user import resolution
from dynamic_user.models import AccountDeletionRequest

pytestmark = pytest.mark.django_db


@pytest.fixture
def client(user: Any) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def other_client(other_user: Any) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=other_user)
    return api_client


# --------------------------------------------------------------------------------- permissions


_ENDPOINTS: list[tuple[str, str, dict[str, Any]]] = [
    ("get", "dynamic-user-me", {}),
    ("get", "dynamic-user-my-profile", {}),
    ("patch", "dynamic-user-my-profile", {}),
    ("get", "dynamic-user-my-setting", {}),
    ("patch", "dynamic-user-my-setting", {}),
    ("get", "dynamic-user-profile-list", {}),
    ("get", "dynamic-user-my-deletion-request", {}),
    ("post", "dynamic-user-my-deletion-request", {}),
    ("delete", "dynamic-user-my-deletion-request", {}),
]


@pytest.mark.parametrize(("method", "url_name", "kwargs"), _ENDPOINTS)
def test_unauthenticated_request_is_rejected(
    appkit_api_client: APIClient, method: str, url_name: str, kwargs: dict[str, Any]
) -> None:
    """DRF's default ``DEFAULT_AUTHENTICATION_CLASSES`` (unmodified here — ``SessionAuthentication``
    first, ``BasicAuthentication`` second) means an anonymous request surfaces as 403, not 401:
    ``APIView.handle_exception`` only keeps a ``NotAuthenticated`` at 401 when
    ``get_authenticate_header()`` returns a non-empty ``WWW-Authenticate`` value, and
    ``SessionAuthentication`` (checked first) returns none. ``error.code`` stays
    ``"not_authenticated"`` regardless — that's what actually distinguishes this from an
    authenticated-but-forbidden request, not the HTTP status."""
    response = getattr(appkit_api_client, method)(
        reverse(url_name, kwargs=kwargs), data={}, format="json"
    )
    appkit_assert_error_envelope(response, code="not_authenticated", status=403)


def test_unauthenticated_profile_detail_request_is_rejected(
    appkit_api_client: APIClient, other_user: Any
) -> None:
    url = reverse("dynamic-user-profile-detail", kwargs={"id": other_user.pk})
    response = appkit_api_client.get(url)
    appkit_assert_error_envelope(response, code="not_authenticated", status=403)


# ------------------------------------------------------------------------------------------ /me/


def test_me_returns_200_for_authenticated_user(client: APIClient, user: Any) -> None:
    response = client.get(reverse("dynamic-user-me"))
    assert response.status_code == 200
    assert response.data["username"] == user.username
    assert "password" not in response.data


def test_me_patch_is_not_allowed(client: APIClient) -> None:
    """No PATCH route exists for ``/me/`` at all (``docs/CONTRACT.md`` §5) —
    ``RetrieveAPIView`` defines no handler for it."""
    response = client.patch(reverse("dynamic-user-me"), {"name": "x"}, format="json")
    assert response.status_code == 405


# ------------------------------------------------------------------------------------ my profile


def test_my_profile_get_returns_the_editable_and_read_union(client: APIClient) -> None:
    response = client.get(reverse("dynamic-user-my-profile"))
    assert response.status_code == 200
    assert set(response.data) == {"bio", "is_public", "id"}


def test_my_profile_put_is_not_allowed(client: APIClient) -> None:
    response = client.put(reverse("dynamic-user-my-profile"), {"bio": "x"}, format="json")
    assert response.status_code == 405


def test_my_profile_patch_updates_editable_fields_via_service(
    client: APIClient, profile: Any
) -> None:
    response = client.patch(
        reverse("dynamic-user-my-profile"), {"bio": "hello", "is_public": False}, format="json"
    )
    assert response.status_code == 200
    assert response.data["bio"] == "hello"
    assert response.data["is_public"] is False
    profile.refresh_from_db()
    assert profile.bio == "hello"
    assert profile.is_public is False


def test_my_profile_patch_ignores_locked_and_foreign_fields(
    client: APIClient, user: Any, profile: Any
) -> None:
    original_username = user.username
    original_profile_pk = profile.pk
    response = client.patch(
        reverse("dynamic-user-my-profile"),
        {
            "bio": "ok",
            "is_staff": True,
            "is_superuser": True,
            "is_active": False,
            "username": "hacked",
            "email": "hacked@example.com",
            "id": 999_999,
            "user": 999_999,
        },
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    profile.refresh_from_db()
    assert user.username == original_username
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_active is True
    assert profile.pk == original_profile_pk
    assert profile.bio == "ok"


def test_my_profile_is_scoped_to_the_requesting_user(
    client: APIClient, other_client: APIClient, profile: Any, other_profile: Any
) -> None:
    """There is no URL id on this route — a second user's PATCH can never reach the first
    user's row, since ``get_object()`` is resolved from ``request.user`` only."""
    other_client.patch(reverse("dynamic-user-my-profile"), {"bio": "mine"}, format="json")
    profile.refresh_from_db()
    other_profile.refresh_from_db()
    assert other_profile.bio == "mine"
    assert profile.bio == ""


# ------------------------------------------------------------------------------------ my setting


def test_my_setting_get_returns_the_editable_and_read_union(client: APIClient) -> None:
    response = client.get(reverse("dynamic-user-my-setting"))
    assert response.status_code == 200
    assert set(response.data) == {"language", "timezone", "notifications_enabled", "id"}


def test_my_setting_put_is_not_allowed(client: APIClient) -> None:
    response = client.put(reverse("dynamic-user-my-setting"), {"language": "fr"}, format="json")
    assert response.status_code == 405


def test_my_setting_patch_updates_editable_fields_via_service(client: APIClient) -> None:
    response = client.patch(reverse("dynamic-user-my-setting"), {"language": "fr"}, format="json")
    assert response.status_code == 200
    assert response.data["language"] == "fr"

    setting = resolution.get_setting_model().objects.get(language="fr")
    assert setting.language == "fr"


def test_my_setting_patch_ignores_locked_and_foreign_fields(client: APIClient, user: Any) -> None:
    original_username = user.username
    response = client.patch(
        reverse("dynamic-user-my-setting"),
        {"language": "fr", "is_staff": True, "id": 999_999, "user": 999_999},
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.username == original_username
    assert user.is_staff is False


# --------------------------------------------------------------------------------- /profiles/


def test_public_profile_list_excludes_private_profiles(
    client: APIClient, profile: Any, other_profile: Any
) -> None:
    profile.is_public = True
    profile.save(update_fields=["is_public"])
    other_profile.is_public = False
    other_profile.save(update_fields=["is_public"])

    response = client.get(reverse("dynamic-user-profile-list"))
    assert response.status_code == 200
    ids = {row["id"] for row in response.data["results"]}
    assert profile.pk in ids
    assert other_profile.pk not in ids
    for row in response.data["results"]:
        assert set(row) == {"id", "bio", "user"}
        assert set(row["user"]) == {"id", "username"}


def test_public_profile_list_is_cached(client: APIClient, profile: Any) -> None:
    profile.is_public = True
    profile.save(update_fields=["is_public"])
    url = reverse("dynamic-user-profile-list")

    first = client.get(url)
    assert first.status_code == 200

    with CaptureQueriesContext(connection) as ctx:
        second = client.get(url)
    assert second.status_code == 200
    assert second.data == first.data
    assert len(ctx.captured_queries) == 0


def test_profile_detail_404s_for_non_owner_when_private(
    client: APIClient, other_client: APIClient, other_user: Any, other_profile: Any
) -> None:
    other_profile.is_public = False
    other_profile.save(update_fields=["is_public"])
    url = reverse("dynamic-user-profile-detail", kwargs={"id": other_user.pk})

    owner_response = other_client.get(url)
    assert owner_response.status_code == 200

    stranger_response = client.get(url)
    assert stranger_response.status_code == 404


def test_profile_detail_200s_for_stranger_when_public(
    client: APIClient, other_user: Any, other_profile: Any
) -> None:
    other_profile.is_public = True
    other_profile.save(update_fields=["is_public"])
    url = reverse("dynamic-user-profile-detail", kwargs={"id": other_user.pk})

    response = client.get(url)
    assert response.status_code == 200
    assert response.data["user"]["username"] == other_user.username


def test_profile_detail_resolves_by_user_id_not_profile_pk(
    client: APIClient, other_user: Any
) -> None:
    """``{id}`` is the target user's id, not the Profile row's own pk
    (``docs/CONTRACT.md`` §10 item 6) — proven by deliberately mismatching them."""
    profile_model = resolution.get_profile_model()
    profile_model.objects.filter(user=other_user).delete()
    mismatched_pk = other_user.pk + 100_000
    profile_model.objects.create(pk=mismatched_pk, user=other_user, is_public=True)
    assert mismatched_pk != other_user.pk

    url = reverse("dynamic-user-profile-detail", kwargs={"id": other_user.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert response.data["id"] == mismatched_pk


# --------------------------------------------------------------------------------- deletion


def test_deletion_request_flow(client: APIClient) -> None:
    url = reverse("dynamic-user-my-deletion-request")

    created = client.post(url, {"reason": "leaving"}, format="json")
    assert created.status_code == 201
    assert created.data["status"] == AccountDeletionRequest.Status.PENDING
    assert created.data["reason"] == "leaving"
    assert "reviewed_by" not in created.data
    assert "user" not in created.data

    duplicate = client.post(url, {}, format="json")
    assert duplicate.status_code == 409

    fetched = client.get(url)
    assert fetched.status_code == 200
    assert fetched.data["id"] == created.data["id"]

    cancelled = client.delete(url)
    assert cancelled.status_code == 204

    duplicate_cancel = client.delete(url)
    assert duplicate_cancel.status_code == 409

    after_cancel = client.get(url)
    assert after_cancel.status_code == 404


# ---------------------------------------------------------------------------------- throttling


def test_all_six_throttle_scopes_are_registered(settings: Any) -> None:
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    for scope in (
        "dynamic_user_me",
        "dynamic_user_profile_update",
        "dynamic_user_setting_update",
        "dynamic_user_profiles_list",
        "dynamic_user_profile_retrieve",
        "dynamic_user_deletion_request",
    ):
        assert scope in rates


_THROTTLE_CASES: list[tuple[str, str, str, dict[str, Any]]] = [
    ("dynamic_user_me", "get", "dynamic-user-me", {}),
    ("dynamic_user_profile_update", "patch", "dynamic-user-my-profile", {}),
    ("dynamic_user_setting_update", "patch", "dynamic-user-my-setting", {}),
    ("dynamic_user_profiles_list", "get", "dynamic-user-profile-list", {}),
    ("dynamic_user_deletion_request", "post", "dynamic-user-my-deletion-request", {}),
]


@pytest.mark.parametrize(("scope", "method", "url_name", "body"), _THROTTLE_CASES)
def test_throttle_scope_returns_429_past_its_rate(
    client: APIClient, scope: str, method: str, url_name: str, body: dict[str, Any]
) -> None:
    """``ScopedRateThrottle.THROTTLE_RATES`` is bound to ``api_settings.DEFAULT_THROTTLE_RATES``
    once, at ``rest_framework.throttling`` import time — ``override_settings`` never reaches it,
    so the rate is patched directly to actually engage a real 429 here (mirrors
    ``cleanup_app/tests/backend/test_admin_views.py``'s own ``test_summary_endpoint_throttles_
    past_its_rate``)."""
    with patch.object(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {**ScopedRateThrottle.THROTTLE_RATES, scope: "1/min"},
    ):
        url = reverse(url_name)
        getattr(client, method)(url, body, format="json")
        second = getattr(client, method)(url, body, format="json")

    assert second.status_code == 429


def test_profile_retrieve_scope_returns_429_past_its_rate(
    client: APIClient, other_user: Any, other_profile: Any
) -> None:
    other_profile.is_public = True
    other_profile.save(update_fields=["is_public"])
    url = reverse("dynamic-user-profile-detail", kwargs={"id": other_user.pk})

    with patch.object(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {**ScopedRateThrottle.THROTTLE_RATES, "dynamic_user_profile_retrieve": "1/min"},
    ):
        first = client.get(url)
        second = client.get(url)

    assert first.status_code == 200
    assert second.status_code == 429
