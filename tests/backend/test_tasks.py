"""Exercises ``dynamic_user.tasks`` (imported at module scope here without the ``celery`` extra
installed, proving it degrades to plain callables per its own module docstring) and the
``process_deletion_requests`` management command that drives the same underlying function for a
host running no Celery worker.

Most of these tests run under ``DELETION_MODE="anonymize"`` rather than the default
``"hard_delete"`` — under hard_delete, a finalized row is cascade-deleted along with the user
(``AccountDeletionRequest.user`` is ``on_delete=CASCADE``), so there would be no row left to
``refresh_from_db()`` and inspect. That deletion-mode behavior is already covered by
``test_services.py``; this file's job is the task/command layer's own query-and-loop logic, which
anonymize mode lets these tests observe directly. One test below (
``test_finalize_due_deletions_hard_delete_removes_the_row_via_cascade``) proves the default mode
explicitly, at this layer.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from dynamic_user import tasks
from dynamic_user.models import AccountDeletionRequest
from dynamic_user.services import DeletionService
from tests.backend import deletion_fixtures

pytestmark = pytest.mark.django_db

_ANONYMIZE_SETTINGS = {
    "DELETION_MODE": "anonymize",
    "DELETION_ANONYMIZE_FUNCTION": "tests.backend.deletion_fixtures.anonymize_user",
}


@pytest.fixture(autouse=True)
def _clear_anonymize_calls() -> None:
    deletion_fixtures.calls.clear()
    yield
    deletion_fixtures.calls.clear()


def _make_request(
    user: object, *, status: str, finalize_at=None, requested_days_ago: int | None = None
) -> AccountDeletionRequest:
    request = AccountDeletionRequest.objects.create(
        user=user, status=status, finalize_at=finalize_at
    )
    if requested_days_ago is not None:
        # requested_at is auto_now_add — .update() bypasses that, so this is how a test
        # backdates it without fighting the field.
        AccountDeletionRequest.objects.filter(pk=request.pk).update(
            requested_at=timezone.now() - timezone.timedelta(days=requested_days_ago)
        )
        request.refresh_from_db()
    return request


# --- finalize_due_deletions -----------------------------------------------------------------


def test_finalize_due_deletions_finalizes_only_due_approved_rows(
    user: object, other_user: object
) -> None:
    now = timezone.now()
    due = _make_request(user, status=AccountDeletionRequest.Status.APPROVED, finalize_at=now)
    not_yet_due = _make_request(
        other_user,
        status=AccountDeletionRequest.Status.APPROVED,
        finalize_at=now + timezone.timedelta(days=1),
    )

    with override_settings(DYNAMIC_USER=_ANONYMIZE_SETTINGS):
        finalized_count = tasks.finalize_due_deletions()

    assert finalized_count == 1
    due.refresh_from_db()
    assert due.status == AccountDeletionRequest.Status.FINALIZED
    not_yet_due.refresh_from_db()
    assert not_yet_due.status == AccountDeletionRequest.Status.APPROVED


def test_finalize_due_deletions_ignores_pending_and_rejected(
    user: object, other_user: object
) -> None:
    now = timezone.now()
    pending = _make_request(user, status=AccountDeletionRequest.Status.PENDING, finalize_at=now)
    rejected = _make_request(
        other_user, status=AccountDeletionRequest.Status.REJECTED, finalize_at=now
    )

    with override_settings(DYNAMIC_USER=_ANONYMIZE_SETTINGS):
        finalized_count = tasks.finalize_due_deletions()

    assert finalized_count == 0
    pending.refresh_from_db()
    assert pending.status == AccountDeletionRequest.Status.PENDING
    rejected.refresh_from_db()
    assert rejected.status == AccountDeletionRequest.Status.REJECTED


def test_finalize_due_deletions_continues_past_a_single_row_failure(
    user: object, other_user: object, admin_user: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The named review item for this phase: one row's failure must not abort the batch."""
    now = timezone.now()
    first = _make_request(user, status=AccountDeletionRequest.Status.APPROVED, finalize_at=now)
    poison = _make_request(
        other_user, status=AccountDeletionRequest.Status.APPROVED, finalize_at=now
    )
    third = _make_request(
        admin_user, status=AccountDeletionRequest.Status.APPROVED, finalize_at=now
    )

    real_finalize = DeletionService.finalize

    def _flaky_finalize(request_id: int) -> None:
        if request_id == poison.pk:
            raise RuntimeError("simulated failure finalizing this row")
        real_finalize(request_id)

    monkeypatch.setattr(DeletionService, "finalize", staticmethod(_flaky_finalize))

    with override_settings(DYNAMIC_USER=_ANONYMIZE_SETTINGS):
        finalized_count = tasks.finalize_due_deletions()

    assert finalized_count == 2
    first.refresh_from_db()
    assert first.status == AccountDeletionRequest.Status.FINALIZED
    third.refresh_from_db()
    assert third.status == AccountDeletionRequest.Status.FINALIZED
    poison.refresh_from_db()
    assert poison.status == AccountDeletionRequest.Status.APPROVED  # untouched, not finalized


def test_finalize_due_deletions_hard_delete_removes_the_row_via_cascade(user: object) -> None:
    """DELETION_MODE's default. Proves at the task layer, not just services.py's own tests, that
    a hard_delete finalize leaves no AccountDeletionRequest row behind to inspect — the count
    returned is still correct even though there's nothing left to refresh_from_db()."""
    now = timezone.now()
    due = _make_request(user, status=AccountDeletionRequest.Status.APPROVED, finalize_at=now)

    finalized_count = tasks.finalize_due_deletions()

    assert finalized_count == 1
    assert not AccountDeletionRequest.objects.filter(pk=due.pk).exists()
    assert not get_user_model().objects.filter(pk=user.pk).exists()


# --- purge_deletion_history ------------------------------------------------------------------


def test_purge_deletion_history_deletes_old_finalized_and_rejected(
    user: object, other_user: object
) -> None:
    old_finalized = _make_request(
        user, status=AccountDeletionRequest.Status.FINALIZED, requested_days_ago=100
    )
    old_rejected = _make_request(
        other_user, status=AccountDeletionRequest.Status.REJECTED, requested_days_ago=100
    )

    deleted_count = tasks.purge_deletion_history(older_than_days=90)

    assert deleted_count == 2
    assert not AccountDeletionRequest.objects.filter(pk=old_finalized.pk).exists()
    assert not AccountDeletionRequest.objects.filter(pk=old_rejected.pk).exists()


def test_purge_deletion_history_never_touches_pending_or_approved_regardless_of_age(
    user: object, other_user: object
) -> None:
    old_pending = _make_request(
        user, status=AccountDeletionRequest.Status.PENDING, requested_days_ago=1000
    )
    old_approved = _make_request(
        other_user, status=AccountDeletionRequest.Status.APPROVED, requested_days_ago=1000
    )

    deleted_count = tasks.purge_deletion_history(older_than_days=1)

    assert deleted_count == 0
    assert AccountDeletionRequest.objects.filter(pk=old_pending.pk).exists()
    assert AccountDeletionRequest.objects.filter(pk=old_approved.pk).exists()


def test_purge_deletion_history_leaves_recent_rows_alone(user: object) -> None:
    recent = _make_request(
        user, status=AccountDeletionRequest.Status.FINALIZED, requested_days_ago=1
    )

    deleted_count = tasks.purge_deletion_history(older_than_days=90)

    assert deleted_count == 0
    assert AccountDeletionRequest.objects.filter(pk=recent.pk).exists()


def test_purge_deletion_history_defaults_to_the_configured_retention_window(user: object) -> None:
    old_finalized = _make_request(
        user, status=AccountDeletionRequest.Status.FINALIZED, requested_days_ago=10
    )

    with override_settings(DYNAMIC_USER={"DELETION_HISTORY_RETENTION_DAYS": 5}):
        deleted_count = tasks.purge_deletion_history()

    assert deleted_count == 1
    assert not AccountDeletionRequest.objects.filter(pk=old_finalized.pk).exists()


# --- process_deletion_requests management command --------------------------------------------


def test_management_command_finalizes_due_rows(user: object) -> None:
    due = _make_request(
        user, status=AccountDeletionRequest.Status.APPROVED, finalize_at=timezone.now()
    )

    with override_settings(DYNAMIC_USER=_ANONYMIZE_SETTINGS):
        call_command("process_deletion_requests")

    due.refresh_from_db()
    assert due.status == AccountDeletionRequest.Status.FINALIZED
