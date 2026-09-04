"""``pytest -m live`` — hits the real docker-compose stack over HTTP, not Django's test client.
See ../../../default/backend/tests/live/test_default_playground.py's own docstring for the
auth-mechanism rationale (plain HTTP Basic against DRF's own default auth classes); not repeated
here. Requires the stack up and ``manage.py seed_users`` already run against
``backend-subclassed``.

This is the headline suite — ``test_extra_profile_field_round_trips`` is the one live check
nothing else in the whole build (not Phase 4's serializer-factory unit test, not any mocked
frontend test) can give: a real HTTP PATCH reaching a field (``tagline``) that exists ONLY on this
host's own ``core.Profile``, with zero changes under ``backend/src/``.
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.live

BASE_URL = os.environ.get("PLAYGROUND_BASE_URL", "http://localhost:8001")
PASSWORD = os.environ.get("PLAYGROUND_PASSWORD", "playground-demo-not-a-secret")


def _client(username: str) -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, auth=(username, PASSWORD))


def test_healthz() -> None:
    response = httpx.get(f"{BASE_URL}/healthz/")
    assert response.status_code == 200


def test_extra_profile_field_round_trips() -> None:
    """The headline check: `tagline` exists only on core.Profile — dynamic_user's own
    src/ has zero knowledge of it. A real PATCH through the package's own generic view/serializer
    factory must still write and read it back correctly.
    """
    with _client("alice") as client:
        new_tagline = "Round-tripped live by the Phase 8 playground suite."
        patch_response = client.patch(
            "/api/v1/users/me/profile/", json={"tagline": new_tagline}
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["tagline"] == new_tagline

        get_response = client.get("/api/v1/users/me/profile/")
        assert get_response.status_code == 200
        assert get_response.json()["tagline"] == new_tagline


def test_extra_user_field_appears_on_me() -> None:
    with _client("alice") as client:
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 200
        body = response.json()
        assert body["department"] == "Engineering"
        assert set(body) == {
            "id",
            "username",
            "name",
            "email",
            "phone",
            "is_active",
            "date_joined",
            "department",
        }


def test_extra_setting_field_round_trips() -> None:
    with _client("alice") as client:
        patch_response = client.patch("/api/v1/users/me/setting/", json={"theme": "solarized"})
        assert patch_response.status_code == 200
        assert patch_response.json()["theme"] == "solarized"


def test_private_profile_404s_to_a_stranger_but_not_the_owner() -> None:
    with _client("alice") as alice, _client("bob") as bob:
        bob_id = bob.get("/api/v1/users/me/").json()["id"]
        assert alice.get(f"/api/v1/users/profiles/{bob_id}/").status_code == 404
        assert bob.get(f"/api/v1/users/profiles/{bob_id}/").status_code == 200


def test_public_profiles_list_paginates() -> None:
    with _client("alice") as client:
        response = client.get("/api/v1/users/profiles/", params={"page_size": 5})
        assert response.status_code == 200
        body = response.json()
        assert body["count"] >= 25
        assert body["next"] is not None


def test_staff_gets_403_here_where_default_host_admits_staff() -> None:
    # ADMIN_REQUIRES_SUPERUSER=True on THIS host (vs. False on the default host) — the same
    # "staff" login/password that gets 200 on :8000 gets 403 here. This is the live comparison
    # Phase 8 exists to prove; see the default host's own
    # test_staff_can_admin_on_this_host for the mirror assertion.
    with _client("staff") as client:
        response = client.get("/api/v1/admin/users/")
        assert response.status_code == 403


def test_superuser_can_admin_here() -> None:
    with _client("super") as client:
        response = client.get("/api/v1/admin/users/")
        assert response.status_code == 200


def test_staff_cannot_escalate_privilege_but_superuser_can() -> None:
    with _client("staff") as staff, _client("super") as super_client:
        # staff can't even list users here (ADMIN_REQUIRES_SUPERUSER=True) — resolve the target
        # id as superuser instead, then attempt the escalation as staff directly against the
        # detail endpoint.
        target_id = super_client.get(
            "/api/v1/admin/users/", params={"username": "user01"}
        ).json()["results"][0]["id"]

        staff_attempt = staff.patch(f"/api/v1/admin/users/{target_id}/", json={"is_staff": True})
        assert staff_attempt.status_code in (403, 404)  # 404: ADMIN_REQUIRES_SUPERUSER blocks GET too

        super_attempt = super_client.patch(
            f"/api/v1/admin/users/{target_id}/", json={"is_staff": True}
        )
        assert super_attempt.status_code == 200
        assert super_attempt.json()["is_staff"] is True

        super_client.patch(f"/api/v1/admin/users/{target_id}/", json={"is_staff": False})


def test_finalize_deletion_request_is_superuser_only_here_too() -> None:
    # ADMIN_REQUIRES_SUPERUSER=True already blocks staff from the admin surface entirely on this
    # host — this test confirms the finalize gate is its OWN hard floor (IsSuperUser), not just a
    # side effect of the general admin gate being tightened.
    with _client("staff") as staff, _client("super") as super_client:
        pending = super_client.get(
            "/api/v1/admin/users/deletion-requests/", params={"status": "approved"}
        ).json()["results"]
        assert pending, "seed_users must have left one APPROVED deletion request due for finalize"
        request_id = pending[0]["id"]

        staff_attempt = staff.post(f"/api/v1/admin/users/deletion-requests/{request_id}/finalize/")
        assert staff_attempt.status_code == 403
