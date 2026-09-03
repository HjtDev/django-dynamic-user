"""Exercises the five ``services.py`` methods implemented in Phase 3 —
``ProfileService.update``, ``SettingService.update``, and ``DeletionService.request``/
``.finalize``/``.cancel``. ``DeletionService.review`` is already covered by
``test_services_review.py`` (Phase 2).

Every signal-emitting method gets a payload-exactness test, matching the connect/disconnect style
``test_services_review.py`` already established. Receivers are always named local functions, not
bare lambdas passed straight to ``.connect()`` — ``Signal.connect`` defaults to ``weak=True``, so
an unassigned lambda has no strong reference keeping it alive and can be garbage-collected before
the signal is even sent.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from dynamic_user import signals
from dynamic_user.models import AccountDeletionRequest
from dynamic_user.resolution import get_profile_model, get_setting_model
from dynamic_user.services import (
    DeletionRequestAlreadyExists,
    DeletionService,
    InvalidDeletionState,
    ProfileService,
    SettingService,
)
from tests.backend import deletion_fixtures

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_anonymize_calls() -> None:
    deletion_fixtures.calls.clear()
    yield
    deletion_fixtures.calls.clear()


# --- ProfileService.update ---------------------------------------------------------------


def test_profile_update_writes_changed_fields_and_sends_exact_payload(user: object) -> None:
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.profile_updated.connect(_receiver)
    try:
        profile = ProfileService.update(user, {"bio": "hello world", "is_public": False})
    finally:
        signals.profile_updated.disconnect(_receiver)

    assert profile.bio == "hello world"
    assert profile.is_public is False
    assert get_profile_model().objects.get(user=user).bio == "hello world"

    assert len(received) == 1
    payload = received[0]
    assert payload["user_id"] == user.pk
    assert set(payload["changed_fields"]) == {"bio", "is_public"}
    assert payload["signal"] is signals.profile_updated


def test_profile_update_sender_is_resolved_model(user: object) -> None:
    received_senders: list[type] = []

    def _receiver(sender, **kwargs) -> None:
        received_senders.append(sender)

    signals.profile_updated.connect(_receiver)
    try:
        ProfileService.update(user, {"bio": "x"})
    finally:
        signals.profile_updated.disconnect(_receiver)

    assert received_senders == [get_profile_model()]


def test_profile_update_excludes_noop_fields_from_changed_fields(user: object) -> None:
    ProfileService.update(user, {"bio": "same", "is_public": True})

    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.profile_updated.connect(_receiver)
    try:
        # "bio" is unchanged (already "same"); only "is_public" actually changes.
        ProfileService.update(user, {"bio": "same", "is_public": False})
    finally:
        signals.profile_updated.disconnect(_receiver)

    assert len(received) == 1
    assert received[0]["changed_fields"] == ["is_public"]


def test_profile_update_with_no_actual_changes_sends_no_signal(user: object) -> None:
    ProfileService.update(user, {"bio": "unchanged"})

    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.profile_updated.connect(_receiver)
    try:
        ProfileService.update(user, {"bio": "unchanged"})
    finally:
        signals.profile_updated.disconnect(_receiver)

    assert received == []


def test_profile_update_creates_row_when_missing(user: object) -> None:
    """A host running AUTO_CREATE_PROFILE=False must not get a crash from a legitimate update."""
    get_profile_model().objects.filter(user=user).delete()
    assert get_profile_model().objects.filter(user=user).count() == 0

    profile = ProfileService.update(user, {"bio": "created on demand"})

    assert profile.bio == "created on demand"
    assert get_profile_model().objects.filter(user=user).count() == 1


# --- SettingService.update ---------------------------------------------------------------


def test_setting_update_writes_changed_fields(user: object) -> None:
    setting = SettingService.update(user, {"language": "fa", "timezone": "Asia/Tehran"})

    assert setting.language == "fa"
    assert setting.timezone == "Asia/Tehran"
    assert get_setting_model().objects.get(user=user).language == "fa"


def test_setting_update_creates_row_when_missing(user: object) -> None:
    get_setting_model().objects.filter(user=user).delete()
    assert get_setting_model().objects.filter(user=user).count() == 0

    setting = SettingService.update(user, {"language": "fa"})

    assert setting.language == "fa"
    assert get_setting_model().objects.filter(user=user).count() == 1


def test_setting_update_emits_no_signal_at_all(user: object) -> None:
    """SettingService.update is not part of the versioned-contract signal surface — no
    dynamic_user signal fires for it, ever."""
    received: list[tuple[str, dict]] = []

    def _make(name: str):
        def _receiver(sender, **kwargs) -> None:
            received.append((name, kwargs))

        return _receiver

    receivers = {
        name: _make(name)
        for name in (
            "profile_created",
            "setting_created",
            "deletion_requested",
            "deletion_reviewed",
            "deletion_finalized",
            "profile_updated",
        )
    }
    for name, receiver in receivers.items():
        getattr(signals, name).connect(receiver)
    try:
        SettingService.update(user, {"language": "fa", "notifications_enabled": False})
    finally:
        for name, receiver in receivers.items():
            getattr(signals, name).disconnect(receiver)

    assert received == []


# --- DeletionService.request --------------------------------------------------------------


def test_request_creates_pending_row_with_computed_finalize_at_and_sends_exact_payload(
    user: object,
) -> None:
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.deletion_requested.connect(_receiver)
    try:
        with override_settings(DYNAMIC_USER={"DELETION_GRACE_PERIOD_DAYS": 5}):
            before = timezone.now()
            deletion_request = DeletionService.request(user, reason="no longer needed")
            after = timezone.now()
    finally:
        signals.deletion_requested.disconnect(_receiver)

    assert deletion_request.status == AccountDeletionRequest.Status.PENDING
    assert deletion_request.reason == "no longer needed"
    assert before + timezone.timedelta(days=5) <= deletion_request.finalize_at
    assert deletion_request.finalize_at <= after + timezone.timedelta(days=5)

    assert len(received) == 1
    payload = received[0]
    assert payload["user_id"] == user.pk
    assert payload["request_id"] == deletion_request.pk
    assert payload["finalize_at"] == deletion_request.finalize_at
    assert set(payload) - {"signal"} == {"user_id", "request_id", "finalize_at"}


def test_request_sender_is_account_deletion_request(user: object) -> None:
    received_senders: list[type] = []

    def _receiver(sender, **kwargs) -> None:
        received_senders.append(sender)

    signals.deletion_requested.connect(_receiver)
    try:
        DeletionService.request(user)
    finally:
        signals.deletion_requested.disconnect(_receiver)

    assert received_senders == [AccountDeletionRequest]


def test_request_raises_if_pending_request_already_exists(
    pending_deletion_request: AccountDeletionRequest, user: object
) -> None:
    with pytest.raises(DeletionRequestAlreadyExists):
        DeletionService.request(user)


def test_request_raises_if_approved_request_already_exists(
    approved_deletion_request: AccountDeletionRequest, user: object
) -> None:
    with pytest.raises(DeletionRequestAlreadyExists):
        DeletionService.request(user)


# --- DeletionService.finalize --------------------------------------------------------------


def test_finalize_hard_delete_removes_user_and_sends_exact_payload(
    approved_deletion_request: AccountDeletionRequest, user: object
) -> None:
    user_id = user.pk
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.deletion_finalized.connect(_receiver)
    try:
        DeletionService.finalize(approved_deletion_request.pk)
    finally:
        signals.deletion_finalized.disconnect(_receiver)

    assert not get_user_model().objects.filter(pk=user_id).exists()

    assert len(received) == 1
    payload = received[0]
    assert payload["user_id"] == user_id
    assert payload["mode"] == "hard_delete"
    assert set(payload) - {"signal"} == {"user_id", "mode"}


def test_finalize_hard_delete_sender_is_account_deletion_request(
    approved_deletion_request: AccountDeletionRequest,
) -> None:
    received_senders: list[type] = []

    def _receiver(sender, **kwargs) -> None:
        received_senders.append(sender)

    signals.deletion_finalized.connect(_receiver)
    try:
        DeletionService.finalize(approved_deletion_request.pk)
    finally:
        signals.deletion_finalized.disconnect(_receiver)

    assert received_senders == [AccountDeletionRequest]


def test_finalize_anonymize_calls_function_and_marks_finalized(
    approved_deletion_request: AccountDeletionRequest, user: object
) -> None:
    with override_settings(
        DYNAMIC_USER={
            "DELETION_MODE": "anonymize",
            "DELETION_ANONYMIZE_FUNCTION": "tests.backend.deletion_fixtures.anonymize_user",
        }
    ):
        DeletionService.finalize(approved_deletion_request.pk)

    assert deletion_fixtures.calls == [user]
    approved_deletion_request.refresh_from_db()
    assert approved_deletion_request.status == AccountDeletionRequest.Status.FINALIZED
    assert get_user_model().objects.filter(pk=user.pk).exists()


def test_finalize_anonymize_sends_exact_payload(
    approved_deletion_request: AccountDeletionRequest, user: object
) -> None:
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.deletion_finalized.connect(_receiver)
    try:
        with override_settings(
            DYNAMIC_USER={
                "DELETION_MODE": "anonymize",
                "DELETION_ANONYMIZE_FUNCTION": "tests.backend.deletion_fixtures.anonymize_user",
            }
        ):
            DeletionService.finalize(approved_deletion_request.pk)
    finally:
        signals.deletion_finalized.disconnect(_receiver)

    assert len(received) == 1
    payload = received[0]
    assert payload["user_id"] == user.pk
    assert payload["mode"] == "anonymize"
    assert set(payload) - {"signal"} == {"user_id", "mode"}


def test_finalize_anonymize_never_issues_a_delete_query(
    approved_deletion_request: AccountDeletionRequest,
) -> None:
    with override_settings(
        DYNAMIC_USER={
            "DELETION_MODE": "anonymize",
            "DELETION_ANONYMIZE_FUNCTION": "tests.backend.deletion_fixtures.anonymize_user",
        }
    ):
        with CaptureQueriesContext(connection) as ctx:
            DeletionService.finalize(approved_deletion_request.pk)

    for query in ctx.captured_queries:
        assert not query["sql"].strip().upper().startswith("DELETE"), query["sql"]


def test_finalize_raises_on_pending_request_rather_than_no_op(
    pending_deletion_request: AccountDeletionRequest,
) -> None:
    with pytest.raises(InvalidDeletionState):
        DeletionService.finalize(pending_deletion_request.pk)
    pending_deletion_request.refresh_from_db()
    assert pending_deletion_request.status == AccountDeletionRequest.Status.PENDING


def test_finalize_raises_on_missing_request() -> None:
    with pytest.raises(InvalidDeletionState):
        DeletionService.finalize(999999)


def test_finalize_anonymize_without_function_fails_closed(
    approved_deletion_request: AccountDeletionRequest, user: object
) -> None:
    with override_settings(DYNAMIC_USER={"DELETION_MODE": "anonymize"}):
        with pytest.raises(ImproperlyConfigured):
            DeletionService.finalize(approved_deletion_request.pk)

    # Fails closed: no partial mutation, and never silently falls back to hard_delete.
    assert get_user_model().objects.filter(pk=user.pk).exists()
    approved_deletion_request.refresh_from_db()
    assert approved_deletion_request.status == AccountDeletionRequest.Status.APPROVED


def test_finalize_anonymize_non_callable_target_fails_closed(
    approved_deletion_request: AccountDeletionRequest,
) -> None:
    with override_settings(
        DYNAMIC_USER={
            "DELETION_MODE": "anonymize",
            "DELETION_ANONYMIZE_FUNCTION": "tests.backend.deletion_fixtures.NOT_CALLABLE",
        }
    ):
        with pytest.raises(ImproperlyConfigured):
            DeletionService.finalize(approved_deletion_request.pk)


def test_finalize_unknown_mode_fails_closed_never_deletes(
    approved_deletion_request: AccountDeletionRequest, user: object
) -> None:
    with override_settings(DYNAMIC_USER={"DELETION_MODE": "soft_delete"}):
        with pytest.raises(ImproperlyConfigured):
            DeletionService.finalize(approved_deletion_request.pk)

    assert get_user_model().objects.filter(pk=user.pk).exists()


# --- DeletionService.cancel -----------------------------------------------------------------


def test_cancel_deletes_pending_request_and_unblocks_a_new_one(
    pending_deletion_request: AccountDeletionRequest, user: object
) -> None:
    DeletionService.cancel(user)

    assert not AccountDeletionRequest.objects.filter(pk=pending_deletion_request.pk).exists()

    # .request() works again immediately — no leftover row blocking it.
    new_request = DeletionService.request(user)
    assert new_request.pk != pending_deletion_request.pk


def test_cancel_raises_if_no_request_exists(user: object) -> None:
    with pytest.raises(InvalidDeletionState):
        DeletionService.cancel(user)


def test_cancel_raises_if_request_is_not_pending(
    approved_deletion_request: AccountDeletionRequest, user: object
) -> None:
    with pytest.raises(InvalidDeletionState):
        DeletionService.cancel(user)
    # Not silently no-op'd away — the approved row is untouched.
    assert AccountDeletionRequest.objects.filter(pk=approved_deletion_request.pk).exists()
