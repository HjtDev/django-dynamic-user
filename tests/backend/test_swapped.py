"""The fully-swapped leg — runs only under ``DJANGO_SETTINGS_MODULE=tests.backend.
settings_swapped`` (selected via ``pytest -k swapped``, matching this filename's stem). Proves
the swap machinery works for real: migrations apply from zero, and every one of this package's
own FK/O2O references resolves to the host's subclass, not ``dynamic_user``'s own defaults.

The module-level ``skipif`` below is the correctness backstop, not just a speed optimization:
under the DEFAULT settings leg (``uv run pytest --create-db``, no ``-k``), ``swapped_app`` isn't
installed and ``get_user_model()`` resolves to ``dynamic_user.User`` — a model with no
``department`` field — so these tests would fail outright rather than usefully skip if collected
under the wrong settings module. ``-k swapped`` on the swapped leg's own invocation still narrows
collection for speed; this guard is what makes leg 1 pass regardless of whether ``-k`` is used.
"""

from __future__ import annotations

import os

import pytest
from django.contrib.auth import get_user_model

from dynamic_user.models import AccountDeletionRequest, ChangeLogEntry
from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        os.environ.get("DJANGO_SETTINGS_MODULE") != "tests.backend.settings_swapped",
        reason="requires DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped",
    ),
]


def test_user_model_is_the_swapped_app_subclass() -> None:
    assert get_user_model()._meta.label_lower == "swapped_app.user"


def test_profile_and_setting_resolve_to_swapped_app_subclasses() -> None:
    assert get_profile_model()._meta.label_lower == "swapped_app.profile"
    assert get_setting_model()._meta.label_lower == "swapped_app.setting"


def test_swapped_user_extra_field_round_trips() -> None:
    user = get_user_model().objects.create_user(
        username="dana", email="dana@example.com", password="pw", department="engineering"
    )
    user.refresh_from_db()
    assert user.department == "engineering"


def test_swapped_profile_extra_field_round_trips() -> None:
    user = get_user_model().objects.create_user(
        username="erin", email="erin@example.com", password="pw"
    )
    profile = get_profile_model().objects.create(user=user, tagline="hello world")
    profile.refresh_from_db()
    assert profile.tagline == "hello world"
    assert profile.bio == ""  # inherited AbstractProfile field still present and defaulted


def test_swapped_setting_extra_field_round_trips() -> None:
    user = get_user_model().objects.create_user(
        username="frank", email="frank@example.com", password="pw"
    )
    setting = get_setting_model().objects.create(user=user, theme="dark")
    setting.refresh_from_db()
    assert setting.theme == "dark"
    assert setting.language == "en"  # inherited AbstractSetting field still present


def test_account_deletion_request_fk_targets_swapped_user() -> None:
    user = get_user_model().objects.create_user(
        username="grace", email="grace@example.com", password="pw"
    )
    request = AccountDeletionRequest.objects.create(user=user)
    assert request.user_id == user.pk
    assert type(request.user) is get_user_model()


def test_change_log_entry_actor_fk_targets_swapped_user() -> None:
    from django.contrib.contenttypes.models import ContentType

    from tests.backend.mixin_app.models import Widget

    user = get_user_model().objects.create_user(
        username="hank", email="hank@example.com", password="pw"
    )
    widget = Widget.objects.create(name="w")
    widget.log_change("name", "w", "widget2", actor=user)

    entry = ChangeLogEntry.objects.get()
    assert entry.actor_id == user.pk
    assert entry.content_type == ContentType.objects.get_for_model(Widget)
