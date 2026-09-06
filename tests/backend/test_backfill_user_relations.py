"""``manage.py backfill_user_relations`` (v1.1.0's documented upgrade step) — the DEFAULT-models
leg. Idempotent, ``--dry-run``, ``--no-signals``, and honors ``AUTO_CREATE_PROFILE``/
``AUTO_CREATE_SETTING`` per the command's own docstring.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings

from dynamic_user import signals
from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = pytest.mark.django_db


def _user_missing_both(username: str) -> object:
    """A user with neither Profile nor Setting — as if created before this app was installed,
    or with both AUTO_CREATE_* settings off."""
    with override_settings(
        DYNAMIC_USER={"AUTO_CREATE_PROFILE": False, "AUTO_CREATE_SETTING": False}
    ):
        return get_user_model().objects.create_user(
            username=username, email=f"{username}@example.com", password="pw"
        )


def test_backfill_creates_missing_profile_and_setting() -> None:
    user = _user_missing_both("backfill1")
    assert not get_profile_model().objects.filter(user=user).exists()
    assert not get_setting_model().objects.filter(user=user).exists()

    call_command("backfill_user_relations")

    assert get_profile_model().objects.filter(user=user).exists()
    assert get_setting_model().objects.filter(user=user).exists()


def test_backfill_is_idempotent() -> None:
    user = _user_missing_both("backfill2")
    call_command("backfill_user_relations")
    assert get_profile_model().objects.filter(user=user).count() == 1

    call_command("backfill_user_relations")  # second run
    assert get_profile_model().objects.filter(user=user).count() == 1
    assert get_setting_model().objects.filter(user=user).count() == 1


def test_backfill_dry_run_creates_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    user = _user_missing_both("backfill3")

    call_command("backfill_user_relations", "--dry-run")

    assert not get_profile_model().objects.filter(user=user).exists()
    assert not get_setting_model().objects.filter(user=user).exists()
    output = capsys.readouterr().out
    assert "would create" in output


def test_backfill_reports_counts(capsys: pytest.CaptureFixture[str]) -> None:
    _user_missing_both("backfill4")
    call_command("backfill_user_relations")
    output = capsys.readouterr().out
    assert "Profile:" in output
    assert "Setting:" in output


def test_backfill_skips_profile_when_auto_create_profile_disabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    user = _user_missing_both("backfill5")
    with override_settings(DYNAMIC_USER={"AUTO_CREATE_PROFILE": False}):
        call_command("backfill_user_relations")
    assert not get_profile_model().objects.filter(user=user).exists()
    assert get_setting_model().objects.filter(user=user).exists()
    output = capsys.readouterr().out
    assert "Profile: AUTO_CREATE_PROFILE is disabled" in output


def test_backfill_emits_created_signals_by_default() -> None:
    user = _user_missing_both("backfill6")
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.profile_created.connect(_receiver)
    try:
        call_command("backfill_user_relations")
    finally:
        signals.profile_created.disconnect(_receiver)

    matching = [event for event in received if event["user_id"] == user.pk]
    assert len(matching) == 1


def test_backfill_no_signals_flag_suppresses_events() -> None:
    user = _user_missing_both("backfill7")
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.profile_created.connect(_receiver)
    try:
        call_command("backfill_user_relations", "--no-signals")
    finally:
        signals.profile_created.disconnect(_receiver)

    matching = [event for event in received if event["user_id"] == user.pk]
    assert matching == []
    # The row is still created — only the signal is suppressed.
    assert get_profile_model().objects.filter(user=user).exists()


def test_backfill_does_not_touch_users_with_existing_rows(user: object) -> None:
    """`user` fixture already has a Profile/Setting via normal auto-provisioning — a backfill
    run must not create a second row for it."""
    call_command("backfill_user_relations")
    assert get_profile_model().objects.filter(user=user).count() == 1
    assert get_setting_model().objects.filter(user=user).count() == 1
