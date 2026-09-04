"""``pytest -m live`` — hits the real docker-compose stack over HTTP, not Django's test client.
Automates the manual checks in Phase 8's plan so they're re-runnable, not just a one-time
transcript. Requires the stack up (``docker compose -f playground/docker-compose.yml up -d
--wait``) and ``manage.py seed_users`` already run against ``backend-default``.

DRF's own default authentication classes are still in effect on this host (this app's own
``config/settings.py`` deliberately doesn't override ``DEFAULT_AUTHENTICATION_CLASSES`` — same
convention as ``tests/backend/settings.py`` in the main repo) — ``SessionAuthentication`` first,
``BasicAuthentication`` second — so a plain ``httpx.Client(auth=(username, password))`` against
the API authenticates with no session/CSRF dance needed.
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.live

BASE_URL = os.environ.get("PLAYGROUND_BASE_URL", "http://localhost:8000")
PASSWORD = os.environ.get("PLAYGROUND_PASSWORD", "playground-demo-not-a-secret")


def _client(username: str) -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, auth=(username, PASSWORD))


def test_healthz() -> None:
    response = httpx.get(f"{BASE_URL}/healthz/")
    assert response.status_code == 200


def test_anonymous_gets_401_or_403_on_me() -> None:
    response = httpx.get(f"{BASE_URL}/api/v1/users/me/")
    assert response.status_code in (401, 403)


def test_me_hides_no_locked_fields_but_they_stay_readonly() -> None:
    with _client("alice") as client:
        response = client.get("/api/v1/users/me/")
        assert response.status_code == 200
        body = response.json()
        assert body["username"] == "alice"
        assert set(body) == {
            "id",
            "username",
            "name",
            "email",
            "phone",
            "is_active",
            "date_joined",
        }


def test_private_profile_404s_to_a_stranger_but_not_the_owner() -> None:
    with _client("alice") as alice, _client("bob") as bob:
        bob_id = bob.get("/api/v1/users/me/").json()["id"]

        stranger_response = alice.get(f"/api/v1/users/profiles/{bob_id}/")
        assert stranger_response.status_code == 404

        owner_response = bob.get(f"/api/v1/users/profiles/{bob_id}/")
        assert owner_response.status_code == 200


def test_public_profiles_list_excludes_private_and_paginates() -> None:
    with _client("alice") as client:
        response = client.get("/api/v1/users/profiles/", params={"page_size": 5})
        assert response.status_code == 200
        body = response.json()
        assert body["count"] >= 25  # the 25 extra plain users + alice, all public by default
        assert body["next"] is not None
        usernames = {row["user"]["username"] for row in body["results"]}
        assert "bob" not in usernames  # private — must never appear in the public list


def test_non_admin_gets_403_on_admin_user_list() -> None:
    with _client("alice") as client:
        response = client.get("/api/v1/admin/users/")
        assert response.status_code == 403


def test_staff_can_admin_on_this_host() -> None:
    # ADMIN_REQUIRES_SUPERUSER=False on the default host — is_staff is sufficient here (the
    # subclassed host's own live suite asserts the opposite for the identical "staff" login).
    with _client("staff") as client:
        response = client.get("/api/v1/admin/users/")
        assert response.status_code == 200


def test_staff_cannot_escalate_privilege_but_superuser_can() -> None:
    with _client("staff") as staff, _client("super") as super_client:
        target_id = staff.get(
            "/api/v1/admin/users/", params={"username": "user01"}
        ).json()["results"][0]["id"]

        staff_attempt = staff.patch(f"/api/v1/admin/users/{target_id}/", json={"is_staff": True})
        assert staff_attempt.status_code == 403

        super_attempt = super_client.patch(
            f"/api/v1/admin/users/{target_id}/", json={"is_staff": True}
        )
        assert super_attempt.status_code == 200
        assert super_attempt.json()["is_staff"] is True

        # revert, so a re-run of this test (or seed_users --reset skipped) stays deterministic
        super_client.patch(f"/api/v1/admin/users/{target_id}/", json={"is_staff": False})


def test_finalize_deletion_request_is_superuser_only_regardless_of_admin_requires_superuser() -> (
    None
):
    with _client("staff") as staff, _client("super") as super_client:
        pending = super_client.get(
            "/api/v1/admin/users/deletion-requests/", params={"status": "approved"}
        ).json()["results"]
        assert pending, "seed_users must have left one APPROVED deletion request due for finalize"
        request_id = pending[0]["id"]

        staff_attempt = staff.post(f"/api/v1/admin/users/deletion-requests/{request_id}/finalize/")
        assert staff_attempt.status_code == 403
