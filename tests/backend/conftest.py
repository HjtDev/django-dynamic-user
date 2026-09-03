"""Shared pytest fixtures for this app's own test suite.

The ``appkit_api_client``/``appkit_user``/``appkit_admin_user``/``appkit_auth_client``/
``appkit_admin_client`` fixtures come from ``-p appkit.testing`` (wired in
``backend/pyproject.toml``'s addopts) — this file only adds fixtures specific to this app's own
models, which appkit's generic fixtures don't know about.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from dynamic_user import resolution
from dynamic_user.models import AccountDeletionRequest


@pytest.fixture(autouse=True)
def _cache_isolation() -> Iterator[None]:
    """Clears Django's cache before and after every test.

    Phase 5 makes two things write to the default ``LocMemCache``: ``CachedListMixin``'s
    ``/profiles/`` snapshot and ``ScopedRateThrottle``'s per-scope request counters. Neither is
    touched by a test's DB transaction rollback, so without this a cached list page or a
    throttle counter from one test leaks into the next and the suite becomes order-dependent
    (mirrors ``cleanup_app/tests/backend/conftest.py``'s own ``_cleanup_cache_isolation``, which
    hit this exact issue first). Autouse is safe here for the same reason it's safe there:
    ``LocMemCache`` is already isolated per pytest-xdist worker process, so there is no *shared*
    external cache an autouse clear could clobber for another worker's in-flight test — unlike
    ``-p appkit.testing``'s own ``appkit_clear_cache``, deliberately *not* autouse for exactly
    that shared-Redis concern.
    """
    cache.clear()
    yield
    cache.clear()


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
def profile(user: object) -> Any:
    model = resolution.get_profile_model()
    obj, _ = cast(Any, model).objects.get_or_create(user=user)
    return obj


@pytest.fixture
def other_profile(other_user: object) -> Any:
    model = resolution.get_profile_model()
    obj, _ = cast(Any, model).objects.get_or_create(user=other_user)
    return obj


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
