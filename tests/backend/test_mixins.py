"""Exercises every mixin in ``dynamic_user.mixins`` against ``tests.backend.mixin_app.Widget``,
the concrete model composing all seven."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from dynamic_user.models import ChangeLogEntry
from tests.backend.mixin_app.models import Widget

pytestmark = pytest.mark.django_db


def test_avatar_mixin_fields_default_empty() -> None:
    widget = Widget.objects.create(name="w")
    assert not widget.avatar
    assert widget.avatar_updated_at is None


def test_timestamp_mixin_sets_created_and_updated() -> None:
    widget = Widget.objects.create(name="w")
    assert widget.created_at is not None
    assert widget.updated_at is not None

    original_updated = widget.updated_at
    widget.name = "renamed"
    widget.save()
    widget.refresh_from_db()
    assert widget.updated_at >= original_updated


def test_history_mixin_log_change_writes_change_log_entry(user: object) -> None:
    widget = Widget.objects.create(name="w")
    widget.log_change("name", "w", "widget", actor=user)

    entry = ChangeLogEntry.objects.get()
    assert entry.content_type == ContentType.objects.get_for_model(Widget)
    assert entry.object_id == widget.pk
    assert entry.field_name == "name"
    assert entry.old_value == "w"
    assert entry.new_value == "widget"
    assert entry.actor_id == user.pk


def test_history_mixin_log_change_actor_is_optional() -> None:
    widget = Widget.objects.create(name="w")
    widget.log_change("name", "w", "widget")

    entry = ChangeLogEntry.objects.get()
    assert entry.actor is None


def test_history_mixin_log_change_stringifies_none() -> None:
    widget = Widget.objects.create(name="w")
    widget.log_change("avatar_updated_at", None, None)

    entry = ChangeLogEntry.objects.get()
    assert entry.old_value == ""
    assert entry.new_value == ""


def test_soft_delete_mixin_default_manager_excludes_deleted() -> None:
    visible = Widget.objects.create(name="visible")
    deleted = Widget.objects.create(name="deleted", is_deleted=True, deleted_at=timezone.now())

    assert list(Widget.objects.all()) == [visible]
    assert set(Widget.all_objects.all()) == {visible, deleted}


def test_verification_mixin_defaults_unverified() -> None:
    widget = Widget.objects.create(name="w")
    assert widget.email_verified is False
    assert widget.email_verified_at is None
    assert widget.phone_verified is False
    assert widget.phone_verified_at is None


def test_last_seen_mixin_fields_are_nullable() -> None:
    widget = Widget.objects.create(name="w")
    assert widget.last_seen_at is None
    assert widget.last_seen_ip is None

    now = timezone.now()
    widget.last_seen_at = now
    widget.last_seen_ip = "127.0.0.1"
    widget.save()
    widget.refresh_from_db()
    assert widget.last_seen_at == now
    assert widget.last_seen_ip == "127.0.0.1"


def test_metadata_mixin_defaults_to_empty_dict() -> None:
    widget = Widget.objects.create(name="w")
    assert widget.metadata == {}

    widget.metadata = {"favorite_color": "blue"}
    widget.save()
    widget.refresh_from_db()
    assert widget.metadata == {"favorite_color": "blue"}


def test_change_log_entry_index_fields_are_queryable(user: object) -> None:
    widget = Widget.objects.create(name="w")
    widget.log_change("name", "w", "widget", actor=user)

    entries = ChangeLogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(Widget), object_id=widget.pk
    )
    assert entries.count() == 1


def test_change_log_entry_changed_at_is_recent() -> None:
    widget = Widget.objects.create(name="w")
    widget.log_change("name", "w", "widget")

    entry = ChangeLogEntry.objects.get()
    assert timezone.now() - entry.changed_at < timedelta(seconds=5)
