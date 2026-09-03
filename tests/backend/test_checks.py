"""Exercises ``dynamic_user.checks.check_deletion_settings`` (``dynamic_user.E003``) — the
system-check backstop for the "anonymize mode needs a real anonymize function" invariant
``services.DeletionService.finalize()`` also enforces at call time (``test_services.py``) — and
``dynamic_user.checks.check_field_allowlists`` (``dynamic_user.E005``), the startup half of the
"unknown allowlist field" guard whose call-time half lives in ``serializers.py`` (see
``test_serializers.py``'s own field-existence tests for that side).
"""

from __future__ import annotations

from django.test import override_settings

from dynamic_user import checks


def test_hard_delete_mode_is_clean() -> None:
    with override_settings(DYNAMIC_USER={"DELETION_MODE": "hard_delete"}):
        errors = checks.check_deletion_settings(None)
    assert errors == []


def test_anonymize_mode_with_a_function_configured_is_clean() -> None:
    with override_settings(
        DYNAMIC_USER={
            "DELETION_MODE": "anonymize",
            "DELETION_ANONYMIZE_FUNCTION": "tests.backend.deletion_fixtures.anonymize_user",
        }
    ):
        errors = checks.check_deletion_settings(None)
    assert errors == []


def test_anonymize_mode_without_a_function_raises_e003() -> None:
    with override_settings(DYNAMIC_USER={"DELETION_MODE": "anonymize"}):
        errors = checks.check_deletion_settings(None)
    assert len(errors) == 1
    assert errors[0].id == "dynamic_user.E003"


def test_unknown_mode_raises_e003() -> None:
    with override_settings(DYNAMIC_USER={"DELETION_MODE": "soft_delete"}):
        errors = checks.check_deletion_settings(None)
    assert len(errors) == 1
    assert errors[0].id == "dynamic_user.E003"


def test_check_never_raises_only_returns() -> None:
    """A system check that raises breaks manage.py entirely, for every command — this must
    always return a list, never propagate an exception, even for a badly-typed setting."""
    with override_settings(DYNAMIC_USER={"DELETION_MODE": None}):
        errors = checks.check_deletion_settings(None)
    assert len(errors) == 1
    assert errors[0].id == "dynamic_user.E003"


# --- dynamic_user.E005 -----------------------------------------------------------------------


def test_default_allowlists_are_clean() -> None:
    """docs/CONTRACT.md §6: a default allowlist can never be the one that's missing, since
    checks.py already requires every swapped model to subclass this package's own abstract
    base."""
    errors = checks.check_field_allowlists(None)
    assert errors == []


def test_unknown_field_in_profile_editable_fields_raises_e005_naming_field_and_key() -> None:
    with override_settings(DYNAMIC_USER={"PROFILE_EDITABLE_FIELDS": ["not_a_real_field"]}):
        errors = checks.check_field_allowlists(None)
    assert len(errors) == 1
    assert errors[0].id == "dynamic_user.E005"
    assert "not_a_real_field" in errors[0].msg
    assert "PROFILE_EDITABLE_FIELDS" in errors[0].msg


def test_unknown_field_in_setting_read_fields_raises_e005() -> None:
    with override_settings(DYNAMIC_USER={"SETTING_READ_FIELDS": ["nope"]}):
        errors = checks.check_field_allowlists(None)
    assert len(errors) == 1
    assert errors[0].id == "dynamic_user.E005"
    assert "SETTING_READ_FIELDS" in errors[0].msg


def test_unknown_field_in_user_privileged_fields_raises_e005() -> None:
    """USER_PRIVILEGED_FIELDS has union, not override, semantics (conf.get_privileged_fields) —
    a host can only add to it, and an added field still has to exist on the resolved user
    model."""
    with override_settings(DYNAMIC_USER={"USER_PRIVILEGED_FIELDS": ["not_real"]}):
        errors = checks.check_field_allowlists(None)
    assert len(errors) == 1
    assert errors[0].id == "dynamic_user.E005"
    assert "not_real" in errors[0].msg


def test_multiple_unknown_fields_report_multiple_errors() -> None:
    with override_settings(
        DYNAMIC_USER={
            "PROFILE_EDITABLE_FIELDS": ["bogus_one"],
            "SETTING_EDITABLE_FIELDS": ["bogus_two"],
        }
    ):
        errors = checks.check_field_allowlists(None)
    assert {e.id for e in errors} == {"dynamic_user.E005"}
    assert len(errors) == 2


def test_field_allowlists_check_never_raises_when_swappable_setting_is_itself_broken() -> None:
    """A malformed DYNAMIC_USER_PROFILE_MODEL is already reported by dynamic_user.E001/E002 —
    this check must skip that model rather than letting resolution.py's own
    ImproperlyConfigured propagate out of a system check."""
    with override_settings(DYNAMIC_USER_PROFILE_MODEL="not-a-valid-label"):
        errors = checks.check_field_allowlists(None)
    assert all(e.id == "dynamic_user.E005" for e in errors)
