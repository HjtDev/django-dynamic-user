"""Phase 6's admin HTTP surface — the fully-swapped leg. Runs only under
``DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped`` (selected via ``pytest -k swapped``,
same guard shape as ``test_views_swapped.py``/``test_swapped.py``).

Proves the admin surface reaches the swapped subclasses' extra fields (``User.department``,
``Profile.tagline``, ``Setting.theme``) over real HTTP with zero package-level code changes, that
filtering picks up a host's own field with zero package changes, and re-runs the
privilege-escalation guard against the swapped user model — a permission bug that only shows up
against a subclassed model would otherwise ship unnoticed.
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
def other_user(db: None) -> Any:
    return get_user_model().objects.create_user(
        username="quinn", email="quinn@example.com", password="pw", department="sales"
    )


@pytest.fixture
def staff_user(db: None) -> Any:
    return get_user_model().objects.create_user(
        username="carol",
        email="carol@example.com",
        password="pw",
        is_staff=True,
        department="support",
    )


@pytest.fixture
def admin_user(db: None) -> Any:
    return get_user_model().objects.create_superuser(
        username="admin", email="admin@example.com", password="pw", department="ops"
    )


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


def test_admin_user_detail_includes_the_swapped_extra_field(
    admin_client: APIClient, other_user: Any
) -> None:
    response = admin_client.get(
        reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    )
    assert response.status_code == 200
    assert response.data["department"] == "sales"


def test_admin_user_list_filters_on_the_swapped_extra_field(
    admin_client: APIClient, other_user: Any, staff_user: Any
) -> None:
    response = admin_client.get(reverse("dynamic-user-admin-user-list"), {"department": "sales"})
    assert response.status_code == 200
    usernames = {row["username"] for row in response.data["results"]}
    assert usernames == {other_user.username}


def test_admin_profile_patch_updates_the_swapped_extra_field(
    admin_client: APIClient, other_user: Any
) -> None:
    url = reverse("dynamic-user-admin-user-profile", kwargs={"id": other_user.pk})
    response = admin_client.patch(url, {"tagline": "hello from admin"}, format="json")
    assert response.status_code == 200
    assert response.data["tagline"] == "hello from admin"

    profile = get_profile_model().objects.get(user=other_user)
    assert profile.tagline == "hello from admin"


def test_admin_setting_patch_updates_the_swapped_extra_field(
    admin_client: APIClient, other_user: Any
) -> None:
    url = reverse("dynamic-user-admin-user-setting", kwargs={"id": other_user.pk})
    response = admin_client.patch(url, {"theme": "dark"}, format="json")
    assert response.status_code == 200
    assert response.data["theme"] == "dark"

    setting = get_setting_model().objects.get(user=other_user)
    assert setting.theme == "dark"


def test_staff_admin_cannot_escalate_privileges_on_the_swapped_user_model(
    staff_client: APIClient, other_user: Any
) -> None:
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = staff_client.patch(url, {"is_staff": True}, format="json")
    assert response.status_code == 403

    other_user.refresh_from_db()
    assert other_user.is_staff is False


def test_staff_admin_can_still_edit_a_non_privileged_swapped_field(
    staff_client: APIClient, other_user: Any
) -> None:
    url = reverse("dynamic-user-admin-user-detail", kwargs={"id": other_user.pk})
    response = staff_client.patch(url, {"department": "engineering"}, format="json")
    assert response.status_code == 200

    other_user.refresh_from_db()
    assert other_user.department == "engineering"
