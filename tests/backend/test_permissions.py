"""Direct unit tests for ``permissions.py``'s two classes, independent of any view.

``MyProfileView``/``MySettingView`` always resolve their object as "the row for
``request.user``" — there is no URL id on either route at all (``docs/CONTRACT.md`` §5) — so no
HTTP-level test against those views can ever construct the foreign-object case
``IsProfileOwner`` exists to deny; removing it from either view's ``permission_classes`` changes
no observable HTTP response. These tests exercise ``has_object_permission()`` directly against a
manufactured mismatch instead, proving the class itself denies correctly — the actual security
property, independent of whether a given view's own object resolution happens to ever reach it.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory

from dynamic_user.permissions import IsProfileOwner, IsPublicOrOwner

pytestmark = pytest.mark.django_db

_factory = APIRequestFactory()


def _request_for(user: Any) -> Any:
    request = _factory.get("/")
    request.user = user
    return request


def test_is_profile_owner_allows_the_owner(user: Any, profile: Any) -> None:
    assert IsProfileOwner().has_object_permission(_request_for(user), None, profile) is True


def test_is_profile_owner_denies_a_foreign_object(user: Any, other_profile: Any) -> None:
    assert IsProfileOwner().has_object_permission(_request_for(user), None, other_profile) is False


def test_is_public_or_owner_allows_the_owner_even_when_private(
    other_user: Any, other_profile: Any
) -> None:
    other_profile.is_public = False
    other_profile.save(update_fields=["is_public"])
    assert (
        IsPublicOrOwner().has_object_permission(_request_for(other_user), None, other_profile)
        is True
    )


def test_is_public_or_owner_allows_a_stranger_when_public(user: Any, other_profile: Any) -> None:
    other_profile.is_public = True
    other_profile.save(update_fields=["is_public"])
    assert IsPublicOrOwner().has_object_permission(_request_for(user), None, other_profile) is True


def test_is_public_or_owner_raises_not_found_for_a_stranger_when_private(
    user: Any, other_profile: Any
) -> None:
    other_profile.is_public = False
    other_profile.save(update_fields=["is_public"])
    with pytest.raises(NotFound):
        IsPublicOrOwner().has_object_permission(_request_for(user), None, other_profile)
