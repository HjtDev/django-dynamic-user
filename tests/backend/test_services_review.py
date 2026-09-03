"""Exercises the one slice of ``services.py`` implemented in Phase 2:
``DeletionService.review`` — pulled forward from Phase 3 so ``admin.py``'s approve/reject action
has something real to call (this phase's plan, decision 2)."""

from __future__ import annotations

import pytest

from dynamic_user import signals
from dynamic_user.models import AccountDeletionRequest
from dynamic_user.services import DeletionService, InvalidDeletionState

pytestmark = pytest.mark.django_db


def test_review_approves_pending_request(
    pending_deletion_request: AccountDeletionRequest, admin_user: object
) -> None:
    result = DeletionService.review(
        pending_deletion_request.pk, approved=True, reviewed_by=admin_user
    )
    assert result.status == AccountDeletionRequest.Status.APPROVED
    assert result.reviewed_by_id == admin_user.pk
    assert result.reviewed_at is not None


def test_review_rejects_pending_request(
    pending_deletion_request: AccountDeletionRequest, admin_user: object
) -> None:
    result = DeletionService.review(
        pending_deletion_request.pk, approved=False, reviewed_by=admin_user
    )
    assert result.status == AccountDeletionRequest.Status.REJECTED


def test_review_sends_deletion_reviewed_signal_with_exact_payload(
    pending_deletion_request: AccountDeletionRequest, admin_user: object
) -> None:
    received: list[dict] = []

    def _receiver(sender, **kwargs) -> None:
        received.append(kwargs)

    signals.deletion_reviewed.connect(_receiver)
    try:
        DeletionService.review(pending_deletion_request.pk, approved=True, reviewed_by=admin_user)
    finally:
        signals.deletion_reviewed.disconnect(_receiver)

    assert len(received) == 1
    payload = received[0]
    assert payload["request_id"] == pending_deletion_request.pk
    assert payload["status"] == AccountDeletionRequest.Status.APPROVED
    assert payload["reviewed_by_id"] == admin_user.pk
    assert payload["signal"] is signals.deletion_reviewed


def test_review_signal_sender_is_account_deletion_request(
    pending_deletion_request: AccountDeletionRequest, admin_user: object
) -> None:
    received_senders: list[type] = []

    def _receiver(sender, **kwargs) -> None:
        received_senders.append(sender)

    signals.deletion_reviewed.connect(_receiver)
    try:
        DeletionService.review(pending_deletion_request.pk, approved=True, reviewed_by=admin_user)
    finally:
        signals.deletion_reviewed.disconnect(_receiver)
    assert received_senders == [AccountDeletionRequest]


def test_review_raises_on_missing_request(admin_user: object) -> None:
    with pytest.raises(InvalidDeletionState):
        DeletionService.review(999999, approved=True, reviewed_by=admin_user)


def test_review_raises_on_already_reviewed_request(
    pending_deletion_request: AccountDeletionRequest, admin_user: object
) -> None:
    DeletionService.review(pending_deletion_request.pk, approved=True, reviewed_by=admin_user)
    with pytest.raises(InvalidDeletionState):
        DeletionService.review(pending_deletion_request.pk, approved=False, reviewed_by=admin_user)


def test_rejection_is_terminal(
    pending_deletion_request: AccountDeletionRequest, admin_user: object
) -> None:
    DeletionService.review(pending_deletion_request.pk, approved=False, reviewed_by=admin_user)
    with pytest.raises(InvalidDeletionState):
        DeletionService.review(pending_deletion_request.pk, approved=True, reviewed_by=admin_user)
