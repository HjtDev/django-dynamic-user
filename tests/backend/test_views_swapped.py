"""Phase 5's self-service HTTP surface — the fully-swapped leg. Runs only under
``DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped`` (selected via ``pytest -k swapped``,
matching this filename's stem — same guard shape as ``test_swapped.py``).

Proves the views reach the swapped subclasses' extra fields (``User.department``,
``Profile.tagline``, ``Setting.theme``) over real HTTP with zero package-level code changes, and
re-runs the two security-critical cases (private-profile 404, locked-field rejection) against
the swapped models too — a permission or serializer bug that only shows up against a subclassed
model would otherwise ship unnoticed.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        os.environ.get("DJANGO_SETTINGS_MODULE") != "tests.backend.settings_swapped",
        reason="requires DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped",
    ),
]


@pytest.fixture
def user(db: None) -> Any:
    return get_user_model().objects.create_user(
        username="priya", email="priya@example.com", password="pw", department="engineering"
    )


@pytest.fixture
def other_user(db: None) -> Any:
    return get_user_model().objects.create_user(
        username="quinn", email="quinn@example.com", password="pw", department="sales"
    )


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


def test_me_includes_the_swapped_user_extra_field(client: APIClient) -> None:
    response = client.get(reverse("dynamic-user-me"))
    assert response.status_code == 200
    assert response.data["department"] == "engineering"


def test_my_profile_patch_updates_the_swapped_extra_field(client: APIClient, user: Any) -> None:
    response = client.patch(
        reverse("dynamic-user-my-profile"), {"tagline": "hello world"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["tagline"] == "hello world"

    profile = get_profile_model().objects.get(user=user)
    assert profile.tagline == "hello world"


def test_my_setting_patch_updates_the_swapped_extra_field(client: APIClient, user: Any) -> None:
    response = client.patch(reverse("dynamic-user-my-setting"), {"theme": "dark"}, format="json")
    assert response.status_code == 200
    assert response.data["theme"] == "dark"

    setting = get_setting_model().objects.get(user=user)
    assert setting.theme == "dark"


def test_my_profile_patch_ignores_locked_and_foreign_fields_on_swapped_user(
    client: APIClient, user: Any
) -> None:
    original_username = user.username
    response = client.patch(
        reverse("dynamic-user-my-profile"),
        {"tagline": "ok", "is_staff": True, "department": "hacked"},
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.username == original_username
    assert user.is_staff is False
    assert user.department == "engineering"  # untouched — not a Profile field


def test_private_profile_404s_for_non_owner_on_swapped_models(
    client: APIClient, other_client: APIClient, other_user: Any
) -> None:
    other_profile = get_profile_model().objects.get(user=other_user)
    other_profile.is_public = False
    other_profile.save(update_fields=["is_public"])
    url = reverse("dynamic-user-profile-detail", kwargs={"id": other_user.pk})

    owner_response = other_client.get(url)
    assert owner_response.status_code == 200

    stranger_response = client.get(url)
    assert stranger_response.status_code == 404


def test_public_profile_list_includes_the_swapped_profile_public_fields(
    client: APIClient, user: Any
) -> None:
    profile = get_profile_model().objects.get(user=user)
    profile.is_public = True
    profile.save(update_fields=["is_public"])

    response = client.get(reverse("dynamic-user-profile-list"))
    assert response.status_code == 200
    # settings_swapped.py declares no PROFILE_PUBLIC_FIELDS override — the default
    # ["id", "bio"] applies here too, proving the factory's default still resolves against the
    # swapped model rather than requiring a host to redeclare every key.
    for row in response.data["results"]:
        assert set(row) == {"id", "bio", "user"}
