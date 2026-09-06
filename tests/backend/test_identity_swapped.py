"""v1.1.0's identity rule, proven against a real host subclass — the fully-swapped leg. Runs
only under ``DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped`` (see ``test_swapped.py``'s
own docstring for why the ``skipif`` guard is a correctness backstop, not just a speed
optimization: ``swapped_app.User`` doesn't exist on the default leg).

Proves the ``CheckConstraint``/username-generation machinery lives on ``AbstractDynamicUser``
and is genuinely inherited — not something that happens to work only for this package's own
concrete ``User`` model.
"""

from __future__ import annotations

import os

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        os.environ.get("DJANGO_SETTINGS_MODULE") != "tests.backend.settings_swapped",
        reason="requires DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped",
    ),
]


def test_swapped_user_with_phone_only() -> None:
    user = get_user_model().objects.create_user(
        phone="+15551237890", password="pw", department="sales"
    )
    assert user.phone == "+15551237890"
    assert user.email is None
    assert user.department == "sales"


def test_swapped_user_with_neither_identity_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        get_user_model().objects.create_user(username="ghost", password="pw", department="ops")


def test_swapped_user_check_constraint_rejects_a_bulk_create() -> None:
    model = get_user_model()
    with pytest.raises(IntegrityError), transaction.atomic():
        model.objects.bulk_create(
            [model(username="bulk-ghost-swapped", email=None, phone=None, department="ops")]
        )


def test_swapped_user_missing_username_is_generated() -> None:
    user = get_user_model().objects.create_user(
        email="gen-swapped@example.com", password="pw", department="eng"
    )
    assert user.username
    assert user.username.startswith("user_")
