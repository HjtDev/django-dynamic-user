"""Exercises ``dynamic_user.validators.run_validators`` — lazy resolution, caching, fail-closed
behavior, and per-call setting freshness."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from dynamic_user import validators


@pytest.fixture(autouse=True)
def _clear_validator_cache() -> None:
    """The module-level resolved-callable cache is process-global — clear it before/after every
    test so one test's cached callable can't leak into another's assertions about import counts.
    """
    validators._resolved_validators.clear()
    yield
    validators._resolved_validators.clear()


def test_empty_setting_runs_nothing() -> None:
    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": []}):
        validators.run_validators("NAME_VALIDATORS", "anything")  # must not raise


def test_missing_dynamic_user_dict_defaults_to_empty_list() -> None:
    # No DYNAMIC_USER dict at all in tests.backend.settings — proves conf.get_setting's default.
    validators.run_validators("NAME_VALIDATORS", "anything")


def test_passing_validator_does_not_raise() -> None:
    path = "tests.backend.validator_fixtures.always_pass"
    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": [path]}):
        validators.run_validators("NAME_VALIDATORS", "irrelevant")


def test_failing_validator_raises_validation_error() -> None:
    path = "tests.backend.validator_fixtures.always_fail"
    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": [path]}):
        with pytest.raises(ValidationError):
            validators.run_validators("NAME_VALIDATORS", "irrelevant")


def test_unresolvable_path_fails_closed_with_validation_error() -> None:
    path = "tests.backend.validator_fixtures.does_not_exist"
    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": [path]}):
        with pytest.raises(ValidationError, match=path):
            validators.run_validators("NAME_VALIDATORS", "irrelevant")


def test_non_callable_target_fails_closed_with_validation_error() -> None:
    path = "tests.backend.validator_fixtures.NOT_CALLABLE"
    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": [path]}):
        with pytest.raises(ValidationError, match="not callable"):
            validators.run_validators("NAME_VALIDATORS", "irrelevant")


def test_resolved_callable_is_cached_by_dotted_path() -> None:
    path = "tests.backend.validator_fixtures.always_pass"
    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": [path]}):
        validators.run_validators("NAME_VALIDATORS", "one")
        validators.run_validators("NAME_VALIDATORS", "two")
    assert path in validators._resolved_validators


def test_setting_change_is_picked_up_without_restart() -> None:
    """The list of dotted paths itself is read fresh every call — only the imported callable is
    cached, per-path. Changing the setting between calls changes what actually runs."""
    fail_path = "tests.backend.validator_fixtures.always_fail"
    pass_path = "tests.backend.validator_fixtures.always_pass"

    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": [fail_path]}):
        with pytest.raises(ValidationError):
            validators.run_validators("NAME_VALIDATORS", "x")

    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": [pass_path]}):
        validators.run_validators("NAME_VALIDATORS", "x")  # must not raise now


def test_multiple_validators_run_in_order_and_stop_at_first_failure() -> None:
    calls: list[str] = []

    def _make(name: str, *, fail: bool):
        def _validator(value: object) -> None:
            calls.append(name)
            if fail:
                raise ValidationError(f"{name} rejected it")

        return _validator

    import tests.backend.validator_fixtures as fixtures

    fixtures.first = _make("first", fail=False)
    fixtures.second = _make("second", fail=True)
    fixtures.third = _make("third", fail=False)

    paths = [
        "tests.backend.validator_fixtures.first",
        "tests.backend.validator_fixtures.second",
        "tests.backend.validator_fixtures.third",
    ]
    with override_settings(DYNAMIC_USER={"NAME_VALIDATORS": paths}):
        with pytest.raises(ValidationError):
            validators.run_validators("NAME_VALIDATORS", "x")

    assert calls == ["first", "second"]
