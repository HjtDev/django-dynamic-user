"""Exercises ``dynamic_user.checks.check_deletion_settings`` (``dynamic_user.E003``) — the
system-check backstop for the "anonymize mode needs a real anonymize function" invariant
``services.DeletionService.finalize()`` also enforces at call time (``test_services.py``).
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
