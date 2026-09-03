"""The mirror image of ``test_partial_swap.py`` — runs only under
``DJANGO_SETTINGS_MODULE=tests.backend.settings_user_swap`` (selected via
``pytest -k user_swap``, matching this filename's stem).

This is the concrete proof that ``migrations.swappable_dependency(settings.AUTH_USER_MODEL)``
needed to be added back into ``dynamic_user/migrations/0001_initial.py`` by hand (see that
file's own comment, and ``docs/CONTRACT.md`` §10 item 14): without it, nothing orders
``user_swap_app``'s migration (creating its ``User`` table) before ``dynamic_user``'s own
migration, which creates ``Profile``/``Setting``/``AccountDeletionRequest``/``ChangeLogEntry`` —
all FK/O2O to ``settings.AUTH_USER_MODEL``. Reaching any assertion below already proves the
migration graph applies in the right order.
"""

from __future__ import annotations

import os

import pytest
from django.contrib.auth import get_user_model

from dynamic_user.models import AccountDeletionRequest
from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        os.environ.get("DJANGO_SETTINGS_MODULE") != "tests.backend.settings_user_swap",
        reason="requires DJANGO_SETTINGS_MODULE=tests.backend.settings_user_swap",
    ),
]


def test_user_model_is_the_user_swap_app_subclass() -> None:
    assert get_user_model()._meta.label_lower == "user_swap_app.user"


def test_profile_and_setting_stay_at_dynamic_users_own_defaults() -> None:
    assert get_profile_model()._meta.label_lower == "dynamic_user.profile"
    assert get_setting_model()._meta.label_lower == "dynamic_user.setting"


def test_default_profile_and_setting_with_swapped_user_round_trip() -> None:
    # AUTO_CREATE_PROFILE/AUTO_CREATE_SETTING (default True, Phase 3) already provisioned both
    # rows for this user — get() proves the round trip on the real auto-provisioned rows.
    user = get_user_model().objects.create_user(
        username="karl", email="karl@example.com", password="pw", department="sales"
    )
    profile = get_profile_model().objects.get(user=user)
    setting = get_setting_model().objects.get(user=user)

    assert profile.user_id == user.pk
    assert setting.user_id == user.pk
    assert user.department == "sales"


def test_account_deletion_request_fk_targets_the_swapped_user() -> None:
    user = get_user_model().objects.create_user(
        username="lena", email="lena@example.com", password="pw"
    )
    request = AccountDeletionRequest.objects.create(user=user)
    assert request.user_id == user.pk
    assert type(request.user) is get_user_model()
