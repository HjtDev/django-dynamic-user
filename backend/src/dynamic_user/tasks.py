"""Celery task(s), behind the ``celery`` extra only.

Phase 3 implements ``dynamic_user.tasks`` per ``docs/CONTRACT.md`` §8 — a task that finalizes an
``AccountDeletionRequest`` once its grace period (``DYNAMIC_USER["DELETION_GRACE_PERIOD_DAYS"]``)
elapses, and ``purge_deletion_history`` (default window
``DYNAMIC_USER["DELETION_HISTORY_RETENTION_DAYS"]``). This app is fully functional with no
Celery worker running at all — a host without Celery drives the same transitions through
``services.DeletionService`` via a management command and plain cron instead.

This module must not hard-import ``celery`` at module scope — a host without the ``celery``
extra installed must be able to import every other part of this package without error.
"""
