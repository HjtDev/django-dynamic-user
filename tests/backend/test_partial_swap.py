"""The partial-swap leg — runs only under
``DJANGO_SETTINGS_MODULE=tests.backend.settings_partial_swap`` (selected via
``pytest -k partial_swap``, matching this filename's stem).

This is the concrete proof behind ``docs/CONTRACT.md`` §10 item 14: ``User`` stays at its
default (``dynamic_user.User``) while ``Profile``/``Setting`` are swapped to a *different*
installed app (``tests.backend.partial_app``). If ``dynamic_user/migrations/0001_initial.py``
carried ``migrations.swappable_dependency()`` for its own ``DYNAMIC_USER_PROFILE_MODEL``/
``DYNAMIC_USER_SETTING_MODEL`` settings, migrating this settings module would raise
``CircularDependencyError`` at collection time, before a single test body even ran — so simply
reaching any assertion below already proves the migration graph is acyclic.

The module-level ``skipif`` below is the correctness backstop for the DEFAULT settings leg
(``uv run pytest --create-db``, no ``-k``), the same reasoning as ``test_swapped.py``'s own —
under default settings, ``get_profile_model()``/``get_setting_model()`` resolve to
``dynamic_user``'s own models, not ``partial_app``'s, so these assertions would fail rather than
usefully skip if collected under the wrong settings module.
"""

from __future__ import annotations

import os

import pytest
from django.contrib.auth import get_user_model

from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        os.environ.get("DJANGO_SETTINGS_MODULE") != "tests.backend.settings_partial_swap",
        reason="requires DJANGO_SETTINGS_MODULE=tests.backend.settings_partial_swap",
    ),
]


def test_user_model_stays_at_the_default() -> None:
    assert get_user_model()._meta.label_lower == "dynamic_user.user"


def test_profile_and_setting_resolve_to_the_separate_partial_app() -> None:
    assert get_profile_model()._meta.label_lower == "partial_app.profile"
    assert get_setting_model()._meta.label_lower == "partial_app.setting"


def test_default_user_with_swapped_profile_and_setting_round_trip() -> None:
    user = get_user_model().objects.create_user(
        username="ivy", email="ivy@example.com", password="pw"
    )
    profile = get_profile_model().objects.create(user=user, tagline="partial swap works")
    setting = get_setting_model().objects.create(user=user, theme="dark")

    profile.refresh_from_db()
    setting.refresh_from_db()
    assert profile.user_id == user.pk
    assert profile.tagline == "partial swap works"
    assert setting.user_id == user.pk
    assert setting.theme == "dark"


def test_profile_still_enforces_one_to_one_across_the_app_boundary() -> None:
    from django.db.utils import IntegrityError

    user = get_user_model().objects.create_user(
        username="jill", email="jill@example.com", password="pw"
    )
    get_profile_model().objects.create(user=user)
    with pytest.raises(IntegrityError):
        get_profile_model().objects.create(user=user)
