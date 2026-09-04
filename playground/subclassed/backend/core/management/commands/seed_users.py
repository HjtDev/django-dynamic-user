"""Seeds the same four personas and password as the default host's own ``seed_users``
(``../../../default/backend/demo/management/commands/seed_users.py``) — see that file's own
docstring for the full personas/pagination/deletion-request rationale, not repeated here.

The one real difference: every seeded user also gets ``department`` set, and ``alice``'s Profile/
Setting get ``tagline``/``theme`` set too — ``core.User``/``core.Profile``/``core.Setting``'s own
extra fields, round-tripped here the same way any other field is, proving they behave like any
other model field with zero dynamic_user code involved.

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
    help = "Seed deterministic playground users on the subclassed host (core.User/Profile/Setting)."

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
                username="super",
                email="super@playground.test",
                password=PASSWORD,
                department="Platform",
            )
            User.objects.create_user(
                username="staff",
                email="staff@playground.test",
                password=PASSWORD,
                is_staff=True,
                department="Support",
            )
            alice = User.objects.create_user(
                username="alice",
                email="alice@playground.test",
                password=PASSWORD,
                name="Alice",
                department="Engineering",
            )
            bob = User.objects.create_user(
                username="bob",
                email="bob@playground.test",
                password=PASSWORD,
                name="Bob",
                department="Sales",
            )

            profile_model = resolution.get_profile_model()
            setting_model = resolution.get_setting_model()

            bob_profile, _ = profile_model.objects.get_or_create(user=bob)
            bob_profile.is_public = False
            bob_profile.bio = "I keep my profile private."
            bob_profile.tagline = "Private by default."
            bob_profile.save(update_fields=["is_public", "bio", "tagline"])

            alice_profile, _ = profile_model.objects.get_or_create(user=alice)
            alice_profile.bio = "Hi, I'm Alice — my profile is public."
            alice_profile.tagline = "core.Profile's own extra field, round-tripped here."
            alice_profile.save(update_fields=["bio", "tagline"])

            alice_setting, _ = setting_model.objects.get_or_create(user=alice)
            alice_setting.theme = "dark"
            alice_setting.save(update_fields=["theme"])

            for i in range(1, EXTRA_USER_COUNT + 1):
                username = f"user{i:02d}"
                User.objects.create_user(
                    username=username,
                    email=f"{username}@playground.test",
                    password=PASSWORD,
                    name=f"Demo User {i:02d}",
                    department="Demo",
                )

            pending_deletion_user = User.objects.create_user(
                username="due-for-deletion",
                email="due-for-deletion@playground.test",
                password=PASSWORD,
            )
            request = DeletionService.request(
                pending_deletion_user,
                reason="Seeded — already due for process_deletion_requests.",
            )
            DeletionService.review(request.pk, approved=True, reviewed_by=super_user)
            AccountDeletionRequest.objects.filter(pk=request.pk).update(
                finalize_at=timezone.now() - timedelta(days=1)
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded 4 personas (super, staff, alice, bob) + {EXTRA_USER_COUNT} plain users "
                "+ 1 due-for-finalize deletion request. alice's profile/setting carry the extra "
                "tagline/theme fields."
            )
        )

    def _reset(self, User: type) -> None:  # noqa: N803
        usernames = ["super", "staff", "alice", "bob", "due-for-deletion"] + [
            f"user{i:02d}" for i in range(1, EXTRA_USER_COUNT + 1)
        ]
        User.objects.filter(username__in=usernames).delete()
