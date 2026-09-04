"""Celery app for the default-host playground — the path that exercises
`dynamic_user.tasks.finalize_due_deletions`/`purge_deletion_history` via a real worker+beat,
rather than the plain-command path the subclassed host exercises instead. Not part of
dynamic_user itself; a host wires this exactly the same way for any Celery app it wants to run.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("playground_default")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Mirrors docs/CONTRACT.md §8's recommended schedule (daily 03:00 / weekly) — registered here via
# beat_schedule rather than django_celery_beat's DB-backed PeriodicTask, since this playground
# runs `celery worker --beat` (the simple, no-extra-service scheduler) not `celery beat` against
# django-celery-beat's own scheduler class.
app.conf.beat_schedule = {
    "finalize-due-deletions": {
        "task": "dynamic_user.tasks.finalize_due_deletions",
        "schedule": crontab(hour=3, minute=0),
    },
    "purge-deletion-history": {
        "task": "dynamic_user.tasks.purge_deletion_history",
        "schedule": crontab(hour=4, minute=0, day_of_week=1),
    },
}
