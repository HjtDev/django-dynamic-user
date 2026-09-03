"""Shared pytest fixtures for this app's own test suite.

The ``appkit_api_client``/``appkit_user``/``appkit_admin_user``/``appkit_auth_client``/
``appkit_admin_client`` fixtures come from ``-p appkit.testing`` (wired in
``backend/pyproject.toml``'s addopts) — this file only adds fixtures specific to this app's own
models, which appkit's generic fixtures don't know about.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from dynamic_user.models import AccountDeletionRequest


@pytest.fixture
def user(db: None) -> object:
    """A plain, non-staff user — distinct from ``appkit_user`` only in name, kept for tests that
    read more naturally with a short fixture name for this app's own default user."""
    return get_user_model().objects.create_user(
        username="alice", email="alice@example.com", password="pw"
    )


@pytest.fixture
def other_user(db: None) -> object:
    return get_user_model().objects.create_user(
        username="bob", email="bob@example.com", password="pw"
    )


@pytest.fixture
def admin_user(db: None) -> object:
    return get_user_model().objects.create_superuser(
        username="admin", email="admin@example.com", password="pw"
    )


@pytest.fixture
def pending_deletion_request(user: object) -> AccountDeletionRequest:
    return AccountDeletionRequest.objects.create(
        user=user,
        status=AccountDeletionRequest.Status.PENDING,
        finalize_at=timezone.now() + timezone.timedelta(days=14),
    )


@pytest.fixture
def approved_deletion_request(user: object) -> AccountDeletionRequest:
    return AccountDeletionRequest.objects.create(
        user=user,
        status=AccountDeletionRequest.Status.APPROVED,
        finalize_at=timezone.now() + timezone.timedelta(days=14),
    )
