"""Exercises the auto-provisioning receivers ``apps.py`` connects from ``signals.py``, and the
exact payload of every signal in ``docs/CONTRACT.md`` §3 not already covered by
``test_services_review.py``/``test_services.py``.

Runs under the DEFAULT settings leg. ``test_swapped.py`` covers the same auto-provisioning
behavior under the fully-swapped leg.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from dynamic_user import signals
from dynamic_user.resolution import get_profile_model, get_setting_model

pytestmark = pytest.mark.django_db


def test_creating_a_user_auto_provisions_profile_and_setting() -> None:
    user = get_user_model().objects.create_user(
        username="ivan", email="ivan@example.com", password="pw"
    )
    assert get_profile_model().objects.filter(user=user).count() == 1
    assert get_setting_model().objects.filter(user=user).count() == 1


def test_saving_an_existing_user_provisions_nothing_extra() -> None:
    user = get_user_model().objects.create_user(
        username="julia", email="julia@example.com", password="pw"
    )
    assert get_profile_model().objects.filter(user=user).count() == 1

    user.name = "Julia"
    user.save()

    assert get_profile_model().objects.filter(user=user).count() == 1
    assert get_setting_model().objects.filter(user=user).count() == 1


def test_profile_created_payload_is_exact() -> None:
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.profile_created.connect(_receiver)
    try:
        user = get_user_model().objects.create_user(
            username="karl", email="karl@example.com", password="pw"
        )
    finally:
        signals.profile_created.disconnect(_receiver)

    assert len(received) == 1
    payload = received[0]
    assert payload["user_id"] == user.pk
    assert payload["signal"] is signals.profile_created
    assert set(payload) - {"signal"} == {"user_id"}


def test_profile_created_sender_is_resolved_model() -> None:
    received_senders: list[type] = []

    def _receiver(sender, **kwargs) -> None:
        received_senders.append(sender)

    signals.profile_created.connect(_receiver)
    try:
        get_user_model().objects.create_user(
            username="liam", email="liam@example.com", password="pw"
        )
    finally:
        signals.profile_created.disconnect(_receiver)

    assert received_senders == [get_profile_model()]


def test_setting_created_payload_is_exact() -> None:
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.setting_created.connect(_receiver)
    try:
        user = get_user_model().objects.create_user(
            username="mia", email="mia@example.com", password="pw"
        )
    finally:
        signals.setting_created.disconnect(_receiver)

    assert len(received) == 1
    payload = received[0]
    assert payload["user_id"] == user.pk
    assert payload["signal"] is signals.setting_created
    assert set(payload) - {"signal"} == {"user_id"}


def test_setting_created_sender_is_resolved_model() -> None:
    received_senders: list[type] = []

    def _receiver(sender, **kwargs) -> None:
        received_senders.append(sender)

    signals.setting_created.connect(_receiver)
    try:
        get_user_model().objects.create_user(
            username="noah", email="noah@example.com", password="pw"
        )
    finally:
        signals.setting_created.disconnect(_receiver)

    assert received_senders == [get_setting_model()]


def test_auto_create_profile_disabled_via_override_settings() -> None:
    """Proves the receiver body re-checks AUTO_CREATE_PROFILE at call time, not just the
    boot-time gate apps.py applies before connecting — the receiver stays connected for the rest
    of the process either way."""
    with override_settings(DYNAMIC_USER={"AUTO_CREATE_PROFILE": False}):
        user = get_user_model().objects.create_user(
            username="olivia", email="olivia@example.com", password="pw"
        )
    assert get_profile_model().objects.filter(user=user).count() == 0


def test_auto_create_setting_disabled_via_override_settings() -> None:
    with override_settings(DYNAMIC_USER={"AUTO_CREATE_SETTING": False}):
        user = get_user_model().objects.create_user(
            username="peter", email="peter@example.com", password="pw"
        )
    assert get_setting_model().objects.filter(user=user).count() == 0


def test_disabling_one_does_not_disable_the_other() -> None:
    with override_settings(DYNAMIC_USER={"AUTO_CREATE_PROFILE": False}):
        user = get_user_model().objects.create_user(
            username="quinn", email="quinn@example.com", password="pw"
        )
    assert get_profile_model().objects.filter(user=user).count() == 0
    assert get_setting_model().objects.filter(user=user).count() == 1
