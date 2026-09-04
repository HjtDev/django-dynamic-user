"""Seeds a deterministic set of users — the ground truth every verification pass in the Phase 8
plan checks the API/admin/frontend against.

Four named personas, same usernames/password on both playground hosts so the SAME login can be
compared side by side at :3000 and :3001:

* ``super`` — superuser. Can do everything on both hosts regardless of ``ADMIN_REQUIRES_SUPERUSER``.
* ``staff`` — ``is_staff=True``, NOT a superuser. Admin on this (default) host
  (``ADMIN_REQUIRES_SUPERUSER=False``); the subclassed host's own ``seed_users`` seeds the same
  username but that host's ``ADMIN_REQUIRES_SUPERUSER=True`` means the identical login gets 403
  there — the live comparison Phase 8 asks for.
* ``alice`` — plain user, public profile (``is_public=True``, the model default).
* ``bob`` — plain user, private profile (``is_public=False``) — the "404 not 403 to a stranger"
  check needs a real private profile to request.

Plus 25 more plain users (``user01``..``user25``) so ``/profiles/`` and the admin user list both
span more than one page at ``appkit.pagination.DefaultPagination``'s default page size.

``AUTO_CREATE_PROFILE``/``AUTO_CREATE_SETTING`` are left at their default (``True``) on this host,
so every user's Profile/Setting row arrives via ``dynamic_user``'s own ``post_save`` receivers,
not created by hand here — seeding this way is itself a live exercise of the
``profile_created``/``setting_created`` signals.

Also seeds one deletion request that is already due for finalization — requested and approved
through ``DeletionService`` (a real exercise of ``deletion_requested``/``deletion_reviewed``), then
backdated via a direct ``.update()`` so ``finalize_due_deletions`` (the Celery beat task on this
host) has something genuine to pick up without needing
``DYNAMIC_USER["DELETION_GRACE_PERIOD_DAYS"]`` overridden away from its documented default of 14.

Idempotent by default (skipped if ``alice`` already exists); ``--reset`` deletes every seeded user
first (cascades Profile/Setting/AccountDeletionRequest via each model's own ``on_delete``).
"""

from __future__ import annotations

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from dynamic_user import resolution
from dynamic_user.models import AccountDeletionRequest
from dynamic_user.services import DeletionService

PASSWORD = os.environ.get("PLAYGROUND_PASSWORD", "playground-demo-not-a-secret")
EXTRA_USER_COUNT = 25


class Command(BaseCommand):
    help = "Seed deterministic playground users — four named personas plus enough plain users to page."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--reset", action="store_true", help="Delete every seeded user before reseeding."
        )

    def handle(self, *args: object, **options: object) -> None:
        User = get_user_model()  # noqa: N806

        if options["reset"]:
            self._reset(User)

        if User.objects.filter(username="alice").exists():
            self.stdout.write("demo users already seeded — pass --reset to reseed.")
            return

        with transaction.atomic():
            super_user = User.objects.create_superuser(
                username="super", email="super@playground.test", password=PASSWORD
            )
            staff_user = User.objects.create_user(
                username="staff",
                email="staff@playground.test",
                password=PASSWORD,
                is_staff=True,
            )
            alice = User.objects.create_user(
                username="alice", email="alice@playground.test", password=PASSWORD, name="Alice"
            )
            bob = User.objects.create_user(
                username="bob", email="bob@playground.test", password=PASSWORD, name="Bob"
            )

            profile_model = resolution.get_profile_model()
            bob_profile, _ = profile_model.objects.get_or_create(user=bob)
            bob_profile.is_public = False
            bob_profile.bio = "I keep my profile private."
            bob_profile.save(update_fields=["is_public", "bio"])

            alice_profile, _ = profile_model.objects.get_or_create(user=alice)
            alice_profile.bio = "Hi, I'm Alice — my profile is public."
            alice_profile.save(update_fields=["bio"])

            for i in range(1, EXTRA_USER_COUNT + 1):
                username = f"user{i:02d}"
                User.objects.create_user(
                    username=username,
                    email=f"{username}@playground.test",
                    password=PASSWORD,
                    name=f"Demo User {i:02d}",
                )

            # A deletion request already due for finalization — real DeletionService calls, then
            # backdated, never DELETION_GRACE_PERIOD_DAYS overridden away from its default.
            pending_deletion_user = User.objects.create_user(
                username="due-for-deletion",
                email="due-for-deletion@playground.test",
                password=PASSWORD,
            )
            request = DeletionService.request(
                pending_deletion_user, reason="Seeded — already due for finalize_due_deletions."
            )
            DeletionService.review(request.pk, approved=True, reviewed_by=super_user)
            AccountDeletionRequest.objects.filter(pk=request.pk).update(
                finalize_at=timezone.now() - timedelta(days=1)
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded 4 personas (super, staff, alice, bob) + {EXTRA_USER_COUNT} plain users "
                "+ 1 due-for-finalize deletion request."
            )
        )

    def _reset(self, User: type) -> None:  # noqa: N803
        usernames = ["super", "staff", "alice", "bob", "due-for-deletion"] + [
            f"user{i:02d}" for i in range(1, EXTRA_USER_COUNT + 1)
        ]
        User.objects.filter(username__in=usernames).delete()
