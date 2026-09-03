"""A thin, Celery-free driver for the account-deletion finalize step — for a host running no
Celery worker at all. Calls ``dynamic_user.tasks.finalize_due_deletions`` directly (the exact same
function ``dynamic_user.tasks.finalize_due_deletions`` the Celery beat schedule would otherwise
call), never a re-implementation of its query/loop logic, so the two drivers can never drift apart.

Intended to be run from plain cron: ``python manage.py process_deletion_requests`` on the same
daily schedule ``docs/CONTRACT.md`` §8 recommends for the Celery task
(``finalize_due_deletions`` — daily at 03:00).
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from dynamic_user.tasks import finalize_due_deletions


class Command(BaseCommand):
    help = (
        "Finalizes every AccountDeletionRequest that is approved and past its grace period "
        "(finalize_at <= now). Equivalent to a single run of the "
        "dynamic_user.tasks.finalize_due_deletions Celery task, for a host running no worker."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        finalized_count = finalize_due_deletions()
        self.stdout.write(
            self.style.SUCCESS(f"Finalized {finalized_count} account deletion request(s).")
        )
