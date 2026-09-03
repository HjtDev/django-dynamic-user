"""Exercises ``serializers.build_serializer()`` and the module-level accessors built on top of
it — the Phase 4 factory every host's subclassed ``Profile``/``Setting``/``User`` PATCH endpoint
depends on.

Runs against the default settings leg (``tests.backend.settings``, which deliberately carries no
``DYNAMIC_USER`` dict — every key here comes from ``conf.DEFAULTS`` unless a test overrides it).
The swapped-model round-trip through a host's own subclass lives in ``test_swapped.py`` instead,
per this repo's file-per-settings-leg convention (``-k swapped`` matches that file's stem).
"""

from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from dynamic_user import serializers
from dynamic_user.resolution import get_profile_model

pytestmark = pytest.mark.django_db


# --- build_serializer(): caching identity -------------------------------------------------


def test_same_arguments_return_the_identical_cached_class() -> None:
    first = serializers.build_serializer(get_profile_model(), ["bio", "is_public"])
    second = serializers.build_serializer(get_profile_model(), ["bio", "is_public"])
    assert first is second


def test_different_read_only_fields_return_a_different_class() -> None:
    writable = serializers.build_serializer(get_profile_model(), ["bio"])
    read_only = serializers.build_serializer(get_profile_model(), ["bio"], read_only_fields=["bio"])
    assert writable is not read_only


def test_different_extra_kwargs_return_a_different_class() -> None:
    plain = serializers.build_serializer(get_profile_model(), ["bio"])
    with_kwargs = serializers.build_serializer(
        get_profile_model(), ["bio"], extra_kwargs={"bio": {"required": True}}
    )
    assert plain is not with_kwargs


def test_accessor_calls_are_cached_too() -> None:
    """The accessors re-read settings on every call (so ``override_settings`` reaches them), but
    with an unchanged setting they still return the identical class underneath, since
    ``build_serializer`` itself is what's cached."""
    assert serializers.get_profile_edit_serializer() is serializers.get_profile_edit_serializer()
    assert serializers.get_user_read_serializer() is serializers.get_user_read_serializer()
    assert (
        serializers.get_public_profile_serializer() is serializers.get_public_profile_serializer()
    )


# --- the password deny-list ----------------------------------------------------------------


def test_password_in_fields_is_refused() -> None:
    with pytest.raises(ImproperlyConfigured, match="password"):
        serializers.build_serializer(get_user_model(), ["username", "password"])


def test_password_reached_via_a_source_alias_is_refused() -> None:
    """The deny-list check inspects every ``extra_kwargs`` ``source=``, not just the literal
    field-name list — a caller can't rename its way past the guard."""
    with pytest.raises(ImproperlyConfigured, match="password"):
        serializers.build_serializer(
            get_user_model(),
            ["username", "secret"],
            extra_kwargs={"secret": {"source": "password"}},
        )


# --- the field-existence guard --------------------------------------------------------------


def test_unknown_field_raises_improperly_configured_naming_the_field() -> None:
    with pytest.raises(ImproperlyConfigured, match="does_not_exist"):
        serializers.build_serializer(get_profile_model(), ["bio", "does_not_exist"])


def test_unknown_field_in_read_only_fields_also_raises() -> None:
    with pytest.raises(ImproperlyConfigured, match="also_missing"):
        serializers.build_serializer(
            get_profile_model(), ["bio"], read_only_fields=["bio", "also_missing"]
        )


def test_unknown_field_reached_through_an_accessor_names_the_setting_key() -> None:
    with override_settings(DYNAMIC_USER={"PROFILE_EDITABLE_FIELDS": ["not_a_real_field"]}):
        with pytest.raises(ImproperlyConfigured) as excinfo:
            serializers.get_profile_edit_serializer()
    message = str(excinfo.value)
    assert "not_a_real_field" in message
    assert "PROFILE_EDITABLE_FIELDS" in message


# --- read-only vs. writable: two calls into the same factory -------------------------------


def test_user_read_serializer_has_every_field_read_only() -> None:
    serializer_cls = serializers.get_user_read_serializer()
    serializer = serializer_cls()
    for name in serializer.fields:
        assert serializer.fields[name].read_only is True


def test_profile_edit_serializer_has_bio_writable() -> None:
    serializer_cls = serializers.get_profile_edit_serializer()
    serializer = serializer_cls()
    assert serializer.fields["bio"].read_only is False


# --- USER_LOCKED_FIELDS subtraction ---------------------------------------------------------


def test_locked_field_is_dropped_from_the_editable_serializer_even_if_host_lists_it() -> None:
    with override_settings(
        DYNAMIC_USER={
            "USER_EDITABLE_FIELDS": ["name", "phone", "is_staff"],
            "USER_LOCKED_FIELDS": ["username", "email", "is_staff", "is_superuser", "is_active"],
        }
    ):
        serializer_cls = serializers.get_user_editable_serializer()
    assert "is_staff" not in serializer_cls().fields
    assert "name" in serializer_cls().fields


# --- public profile nesting ------------------------------------------------------------------


def test_public_profile_serializer_nests_user_public_fields() -> None:
    serializer_cls = serializers.get_public_profile_serializer()
    serializer = serializer_cls()
    assert "user" in serializer.fields
    user_field = serializer.fields["user"]
    assert user_field.read_only is True
    assert set(user_field.fields) == set(serializers.get_user_public_serializer()().fields)


def test_public_profile_serializer_is_cached_across_calls() -> None:
    assert (
        serializers.get_public_profile_serializer() is serializers.get_public_profile_serializer()
    )


# --- admin full-fields builds -----------------------------------------------------------------


def test_admin_user_serializer_includes_real_fields_and_excludes_password() -> None:
    serializer = serializers.get_admin_user_serializer()()
    assert "username" in serializer.fields
    assert "is_staff" in serializer.fields
    assert "groups" in serializer.fields
    assert "password" not in serializer.fields


def test_admin_profile_serializer_includes_every_real_field() -> None:
    serializer = serializers.get_admin_profile_serializer()()
    assert set(serializer.fields) >= {"bio", "is_public", "user"}


def test_admin_setting_serializer_includes_every_real_field() -> None:
    serializer = serializers.get_admin_setting_serializer()()
    assert set(serializer.fields) >= {"language", "timezone", "notifications_enabled"}


# --- override_settings actually reaches the wired accessors (proves lazy, not import-time) ---


def test_override_settings_changes_what_the_next_accessor_call_returns() -> None:
    before = serializers.get_profile_edit_serializer()()
    assert "bio" in before.fields

    with override_settings(DYNAMIC_USER={"PROFILE_EDITABLE_FIELDS": ["is_public"]}):
        during = serializers.get_profile_edit_serializer()()
        assert "bio" not in during.fields
        assert "is_public" in during.fields

    after = serializers.get_profile_edit_serializer()()
    assert "bio" in after.fields


# --- deterministic __name__ -------------------------------------------------------------------


def test_generated_name_is_deterministic_and_key_dependent() -> None:
    one = serializers.build_serializer(get_profile_model(), ["bio"])
    two = serializers.build_serializer(get_profile_model(), ["bio"])
    three = serializers.build_serializer(get_profile_model(), ["bio", "is_public"])

    assert one.__name__ == two.__name__
    assert one.__name__ != three.__name__
    assert re.fullmatch(r"Profile[0-9A-F]{6}Serializer", one.__name__)


# --- setting.SETTING accessors ----------------------------------------------------------------


def test_setting_read_serializer_is_union_of_editable_and_read_fields() -> None:
    serializer = serializers.get_setting_read_serializer()()
    assert set(serializer.fields) == {
        "language",
        "timezone",
        "notifications_enabled",
        "id",
    }
    for name in serializer.fields:
        assert serializer.fields[name].read_only is True


def test_setting_edit_serializer_is_writable() -> None:
    serializer = serializers.get_setting_edit_serializer()()
    assert serializer.fields["language"].read_only is False
