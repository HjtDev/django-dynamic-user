"""v1.1.0's documented upgrade step: create a Profile and/or Setting row for every existing user
missing one — a host installing this app for the first time onto a project that already has
users, or a host that ran with ``AUTO_CREATE_PROFILE``/``AUTO_CREATE_SETTING`` disabled for a
while, needs this so an API/dashboard read never 404s simply because the row was never created
(``docs/CONTRACT.md`` §1's "guarantee these related objects always exist" goal).

Deliberately **not** a data migration: this package cannot safely reach a host's *swapped*
Profile/Setting model from its own migration graph without risking the exact
``CircularDependencyError`` already recorded and proven-absent by
``tests/backend/test_partial_swap.py`` (``docs/CONTRACT.md`` §10 item 14) — a migration that
imported ``resolution.get_profile_model()`` would need a dependency on whatever app that resolves
to, which may not even be known until the host's own settings are read. A management command has
no such constraint: it runs after every app's migrations are already applied, so
``resolution.py`` resolves safely.

Idempotent: a second run against an already-backfilled project creates nothing and reports zero
either way — every insert is a ``get_or_create``, the identical operation
``signals._provision_profile``/``_provision_setting`` already performs per-row on ``post_save``.
"""

from __future__ import annotations

from typing import Any, cast

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Model

from dynamic_user import conf, resolution
from dynamic_user.signals import profile_created, setting_created

_BATCH_SIZE = 500


class Command(BaseCommand):
    help = (
        "Creates a Profile and/or Setting row for every existing user missing one. Idempotent — "
        "safe to run repeatedly. Honors AUTO_CREATE_PROFILE/AUTO_CREATE_SETTING: a model disabled "
        "by either setting is skipped entirely, not backfilled anyway."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would be created without creating them.",
        )
        parser.add_argument(
            "--no-signals",
            action="store_true",
            help=(
                "Suppress profile_created/setting_created for rows created by this run — a "
                "large backfill firing one signal per row can flood a host's own receivers "
                "(e.g. a welcome-email hook) with events that don't represent a real signup."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = options["dry_run"]
        emit_signals = not options["no_signals"]

        if conf.get_setting("AUTO_CREATE_PROFILE"):
            profile_count = self._backfill(
                resolution.get_profile_model(),
                signal=profile_created if emit_signals else None,
                dry_run=dry_run,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Profile: {'would create' if dry_run else 'created'} {profile_count} row(s)."
                )
            )
        else:
            self.stdout.write("Profile: AUTO_CREATE_PROFILE is disabled — skipped.")

        if conf.get_setting("AUTO_CREATE_SETTING"):
            setting_count = self._backfill(
                resolution.get_setting_model(),
                signal=setting_created if emit_signals else None,
                dry_run=dry_run,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Setting: {'would create' if dry_run else 'created'} {setting_count} row(s)."
                )
            )
        else:
            self.stdout.write("Setting: AUTO_CREATE_SETTING is disabled — skipped.")

    def _backfill(self, model: type[Model], *, signal: Any, dry_run: bool) -> int:
        """Not part of this command's public surface. ``model`` is the resolved Profile or
        Setting model — either way it has a ``user`` O2O, iterated in batches via ``.iterator()``
        so a large user table is never loaded into memory at once."""
        from django.contrib.auth import get_user_model

        existing_user_ids = cast(Any, model)._default_manager.values_list("user_id", flat=True)
        missing_users = (
            get_user_model()
            ._default_manager.exclude(pk__in=existing_user_ids)
            .order_by("pk")
            .iterator(chunk_size=_BATCH_SIZE)
        )

        created_count = 0
        for user in missing_users:
            if dry_run:
                created_count += 1
                continue
            _, was_created = cast(Any, model).objects.get_or_create(user=user)
            if was_created:
                created_count += 1
                if signal is not None:
                    signal.send(sender=model, user_id=user.pk)
        return created_count
