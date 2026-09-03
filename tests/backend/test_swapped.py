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

from dynamic_user import serializers
from dynamic_user.models import AccountDeletionRequest, ChangeLogEntry
from dynamic_user.resolution import get_profile_model, get_setting_model
from dynamic_user.services import DeletionService

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
    # AUTO_CREATE_PROFILE (default True, Phase 3) already provisioned a row for this user —
    # updating it in place proves the extra field round-trips on the real auto-provisioned row,
    # rather than fighting the OneToOne constraint with a second create().
    user = get_user_model().objects.create_user(
        username="erin", email="erin@example.com", password="pw"
    )
    profile = get_profile_model().objects.get(user=user)
    profile.tagline = "hello world"
    profile.save(update_fields=["tagline"])
    profile.refresh_from_db()
    assert profile.tagline == "hello world"
    assert profile.bio == ""  # inherited AbstractProfile field still present and defaulted


def test_swapped_setting_extra_field_round_trips() -> None:
    user = get_user_model().objects.create_user(
        username="frank", email="frank@example.com", password="pw"
    )
    setting = get_setting_model().objects.get(user=user)
    setting.theme = "dark"
    setting.save(update_fields=["theme"])
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


def test_auto_provisioning_creates_swapped_profile_and_setting() -> None:
    """Phase 3's first real exercise of the swap machinery: the post_save receiver must reach
    Profile/Setting through resolution.py, never a concrete dynamic_user.Profile/Setting import
    — this is exactly what would silently create the WRONG rows under this settings module if
    that rule were ever violated."""
    user = get_user_model().objects.create_user(
        username="iris", email="iris@example.com", password="pw"
    )
    profile = get_profile_model().objects.get(user=user)
    setting = get_setting_model().objects.get(user=user)
    assert type(profile) is get_profile_model()
    assert type(setting) is get_setting_model()


def test_profile_edit_serializer_includes_the_swapped_app_extra_field() -> None:
    """``settings_swapped.py``'s own ``DYNAMIC_USER["PROFILE_EDITABLE_FIELDS"]`` (Phase 4) lists
    ``tagline`` — proving the factory resolves the field against ``swapped_app.Profile``, not a
    hardcoded ``dynamic_user.Profile``."""
    serializer_cls = serializers.get_profile_edit_serializer()
    assert serializer_cls.Meta.model is get_profile_model()
    assert "tagline" in serializer_cls().fields


def test_profile_edit_serializer_patch_round_trip_sets_the_swapped_field() -> None:
    """A full PATCH round trip — validate and save, not just instantiate — through the Phase 4
    factory's own serializer class."""
    user = get_user_model().objects.create_user(
        username="liam", email="liam@example.com", password="pw"
    )
    profile = get_profile_model().objects.get(user=user)

    serializer = serializers.get_profile_edit_serializer()(
        profile, data={"tagline": "swapped tagline"}, partial=True
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    profile.refresh_from_db()
    assert profile.tagline == "swapped tagline"


def test_setting_edit_serializer_patch_round_trip_sets_the_swapped_field() -> None:
    user = get_user_model().objects.create_user(
        username="maya", email="maya@example.com", password="pw"
    )
    setting = get_setting_model().objects.get(user=user)

    serializer = serializers.get_setting_edit_serializer()(
        setting, data={"theme": "dark"}, partial=True
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    setting.refresh_from_db()
    assert setting.theme == "dark"


def test_user_read_serializer_includes_the_swapped_app_extra_field() -> None:
    user = get_user_model().objects.create_user(
        username="noah", email="noah@example.com", password="pw", department="engineering"
    )
    serializer = serializers.get_user_read_serializer()(user)
    assert serializer.data["department"] == "engineering"


def test_deletion_request_review_finalize_round_trip_against_swapped_models() -> None:
    user = get_user_model().objects.create_user(
        username="jack", email="jack@example.com", password="pw"
    )
    admin = get_user_model().objects.create_superuser(
        username="kate", email="kate@example.com", password="pw"
    )

    deletion_request = DeletionService.request(user)
    assert deletion_request.status == AccountDeletionRequest.Status.PENDING

    reviewed = DeletionService.review(deletion_request.pk, approved=True, reviewed_by=admin)
    assert reviewed.status == AccountDeletionRequest.Status.APPROVED

    DeletionService.finalize(deletion_request.pk)
    assert not get_user_model().objects.filter(pk=user.pk).exists()
