"""Celery task(s), behind the ``celery`` extra only.

Implements ``docs/CONTRACT.md`` §8 — a task that finalizes an ``AccountDeletionRequest`` once its
grace period (``DYNAMIC_USER["DELETION_GRACE_PERIOD_DAYS"]``) elapses, and
``purge_deletion_history`` (default window ``DYNAMIC_USER["DELETION_HISTORY_RETENTION_DAYS"]``).
This app is fully functional with no Celery worker running at all — a host without Celery drives
the same transitions through ``services.DeletionService`` via
``management/commands/process_deletion_requests.py`` and plain cron instead, calling the exact
same underlying function this module's own task calls.

This module must not hard-import ``celery`` at module scope — a host without the ``celery`` extra
installed must be able to import every other part of this package without error. When ``celery``
is not installed, ``shared_task`` degrades to a no-op decorator so
``finalize_due_deletions``/``purge_deletion_history`` stay plain, directly callable functions —
exactly what the management command needs.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from django.utils import timezone

from dynamic_user import conf
from dynamic_user.models import AccountDeletionRequest
from dynamic_user.services import DeletionService

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

try:
    from celery import shared_task
except ImportError:  # celery extra not installed

    def shared_task(*args: Any, **kwargs: Any) -> Callable[[_F], _F]:
        """Degrades ``@shared_task(...)`` to a no-op decorator when ``celery`` isn't installed,
        so the functions below stay importable and directly callable either way."""

        def decorator(func: _F) -> _F:
            return func

        return decorator


@shared_task(name="dynamic_user.tasks.finalize_due_deletions")
def finalize_due_deletions() -> int:
    """Queries ``AccountDeletionRequest`` where ``status=APPROVED`` and ``finalize_at<=now()``,
    calls ``DeletionService.finalize(row.id)`` per row. Continues past a single row's failure
    (logs it) rather than aborting the whole batch — one bad row must never block every other
    user's deletion from finalizing on schedule. Returns the count actually finalized.
    """
    due_ids = list(
        AccountDeletionRequest.objects.filter(
            status=AccountDeletionRequest.Status.APPROVED,
            finalize_at__lte=timezone.now(),
        ).values_list("pk", flat=True)
    )

    finalized_count = 0
    for request_id in due_ids:
        try:
            DeletionService.finalize(request_id)
        except Exception:
            logger.exception(
                "finalize_due_deletions: failed to finalize AccountDeletionRequest %s",
                request_id,
            )
            continue
        finalized_count += 1

    return finalized_count


@shared_task(name="dynamic_user.tasks.purge_deletion_history")
def purge_deletion_history(older_than_days: int | None = None) -> int:
    """Deletes ``FINALIZED``/``REJECTED`` ``AccountDeletionRequest`` rows older than
    ``older_than_days`` (defaults to ``DYNAMIC_USER["DELETION_HISTORY_RETENTION_DAYS"]``). Never
    touches ``PENDING``/``APPROVED`` rows regardless of age. Returns the count deleted.

    Age is measured against ``requested_at`` (``auto_now_add``, never null) rather than
    ``reviewed_at`` (nullable — a request can be finalized without ever being reviewed by a human
    under some host flows) or a ``finalized_at`` the model doesn't have.
    """
    if older_than_days is None:
        older_than_days = conf.get_setting("DELETION_HISTORY_RETENTION_DAYS")

    cutoff = timezone.now() - timedelta(days=older_than_days)
    deleted_count, _ = AccountDeletionRequest.objects.filter(
        status__in=[
            AccountDeletionRequest.Status.FINALIZED,
            AccountDeletionRequest.Status.REJECTED,
        ],
        requested_at__lt=cutoff,
    ).delete()
    return deleted_count
