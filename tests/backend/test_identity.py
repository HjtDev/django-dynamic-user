"""v1.1.0's identity rule (docs/CONTRACT.md §1): both ``email``/``phone`` are optional, at least
one is required, and a missing ``username`` is auto-generated — enforced at the model layer
(``AbstractDynamicUser.save()``/``.clean()``) so no creation path can bypass it, and backstopped
by a DB-level ``CheckConstraint`` for a caller that bypasses ``save()`` entirely.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from dynamic_user.usernames import generate_username

pytestmark = pytest.mark.django_db


# --- creation matrix ----------------------------------------------------------------------


def test_create_user_with_email_only() -> None:
    user = get_user_model().objects.create_user(email="email-only@example.com", password="pw")
    assert user.email == "email-only@example.com"
    assert user.phone is None
    assert user.username


def test_create_user_with_phone_only() -> None:
    user = get_user_model().objects.create_user(phone="+15551234567", password="pw")
    assert user.phone == "+15551234567"
    assert user.email is None
    assert user.username


def test_create_user_with_both_email_and_phone() -> None:
    user = get_user_model().objects.create_user(
        username="carol", email="carol@example.com", phone="+15559876543", password="pw"
    )
    assert user.email == "carol@example.com"
    assert user.phone == "+15559876543"


def test_create_user_with_neither_email_nor_phone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        get_user_model().objects.create_user(username="ghost", password="pw")


def test_model_instance_save_with_neither_identity_field_is_rejected() -> None:
    """The rule holds through a bare ``Model(...).save()`` call too — not only through
    ``UserManager.create_user`` — since an external provisioning path (e.g.
    ``UserProvisioningService.get_or_create``) never goes through the manager at all."""
    user = get_user_model()(username="ghost2")
    with pytest.raises(ValidationError):
        user.save()


def test_check_constraint_rejects_a_row_save_never_sees() -> None:
    """The DB-level ``CheckConstraint`` is the un-bypassable floor: ``bulk_create`` skips
    ``Model.save()`` entirely, so this is the one path this test needs to hit it directly."""
    model = get_user_model()
    with pytest.raises(IntegrityError), transaction.atomic():
        model.objects.bulk_create([model(username="bulk-ghost", email=None, phone=None)])


# --- empty-string normalization -------------------------------------------------------------


def test_empty_string_email_normalizes_to_none() -> None:
    user = get_user_model().objects.create_user(phone="+15551110000", password="pw")
    user.email = ""
    user.save(update_fields=["email"])
    user.refresh_from_db()
    assert user.email is None


def test_empty_string_phone_normalizes_to_none() -> None:
    user = get_user_model().objects.create_user(email="norm@example.com", password="pw")
    user.phone = ""
    user.save(update_fields=["phone"])
    user.refresh_from_db()
    assert user.phone is None


def test_second_user_with_blank_phone_does_not_collide() -> None:
    """Regression: before v1.1.0's normalization, two users saved with phone="" would violate
    the unique index instead of being treated as "no phone."""
    get_user_model().objects.create_user(email="a@example.com", password="pw", phone="")
    second = get_user_model().objects.create_user(email="b@example.com", password="pw", phone="")
    assert second.pk is not None
    assert second.phone is None


# --- username generation --------------------------------------------------------------------


def test_missing_username_is_generated() -> None:
    user = get_user_model().objects.create_user(email="gen@example.com", password="pw")
    assert user.username
    assert user.username.startswith("user_")


def test_generated_usernames_are_unique_across_a_volume_run() -> None:
    users = [
        get_user_model().objects.create_user(email=f"vol{i}@example.com", password="pw")
        for i in range(25)
    ]
    usernames = {u.username for u in users}
    assert len(usernames) == 25


def test_username_auto_generate_disabled_raises_instead_of_generating() -> None:
    with override_settings(DYNAMIC_USER={"USERNAME_AUTO_GENERATE": False}):
        with pytest.raises(ValidationError):
            get_user_model().objects.create_user(email="strict@example.com", password="pw")


def test_username_generator_setting_is_honored() -> None:
    with override_settings(
        DYNAMIC_USER={
            "USERNAME_GENERATOR": "tests.backend.username_fixtures.custom_username_generator"
        }
    ):
        user = get_user_model().objects.create_user(email="customgen@example.com", password="pw")
        assert user.username.startswith("custom-")


def test_username_generator_not_callable_is_improperly_configured() -> None:
    from django.core.exceptions import ImproperlyConfigured

    with override_settings(
        DYNAMIC_USER={"USERNAME_GENERATOR": "tests.backend.username_fixtures.NOT_CALLABLE"}
    ):
        with pytest.raises(ImproperlyConfigured):
            get_user_model().objects.create_user(email="notcallable@example.com", password="pw")


def test_username_generator_bad_path_is_improperly_configured() -> None:
    from django.core.exceptions import ImproperlyConfigured

    with override_settings(DYNAMIC_USER={"USERNAME_GENERATOR": "nope.not.a.real.module"}):
        with pytest.raises(ImproperlyConfigured):
            get_user_model().objects.create_user(email="badgen@example.com", password="pw")


def test_username_prefix_setting_is_honored() -> None:
    with override_settings(DYNAMIC_USER={"USERNAME_PREFIX": "acct_"}):
        user = get_user_model().objects.create_user(email="prefixed@example.com", password="pw")
        assert user.username.startswith("acct_")


def test_generate_username_helper_checks_for_collision(user: object) -> None:
    """A username colliding with an existing row is never returned by the built-in generator —
    exercised directly against usernames.py rather than through save()'s retry path."""
    model = get_user_model()
    for _ in range(20):
        candidate = generate_username(model)
        assert not model.objects.filter(username=candidate).exists()


# --- no username, no name --------------------------------------------------------------------


def test_create_user_without_name() -> None:
    user = get_user_model().objects.create_user(email="noname@example.com", password="pw")
    assert user.name == ""


def test_create_superuser_without_email_or_username() -> None:
    """createsuperuser's REQUIRED_FIELDS is now [] (was ["email"]) — a superuser can be created
    knowing only a phone number, same as any other user."""
    user = get_user_model().objects.create_superuser(phone="+15550009999", password="pw")
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.username


# --- validators wired through the identity rule -----------------------------------------------


def test_phone_validators_run_on_save() -> None:
    with override_settings(
        DYNAMIC_USER={"PHONE_VALIDATORS": ["tests.backend.validator_fixtures.always_fail"]}
    ):
        with pytest.raises(ValidationError):
            get_user_model().objects.create_user(phone="+15551234567", password="pw")


def test_name_validators_run_on_save() -> None:
    with override_settings(
        DYNAMIC_USER={"NAME_VALIDATORS": ["tests.backend.validator_fixtures.always_fail"]}
    ):
        with pytest.raises(ValidationError):
            get_user_model().objects.create_user(
                email="named@example.com", password="pw", name="Alice"
            )


def test_validators_are_skipped_when_field_is_empty() -> None:
    """NAME_VALIDATORS never runs against an empty name — nothing to validate."""
    with override_settings(
        DYNAMIC_USER={"NAME_VALIDATORS": ["tests.backend.validator_fixtures.always_fail"]}
    ):
        user = get_user_model().objects.create_user(email="unnamed@example.com", password="pw")
        assert user.name == ""


# --- update_fields skip path -------------------------------------------------------------------


def test_save_with_update_fields_not_touching_identity_skips_revalidation(user: object) -> None:
    """django.contrib.auth.models.update_last_login calls exactly this shape
    (save(update_fields=["last_login"])) on every login — it must never raise even though this
    row's identity fields aren't in update_fields."""
    from django.utils import timezone as tz

    user.last_login = tz.now()
    user.save(update_fields=["last_login"])  # must not raise
    user.refresh_from_db()
    assert user.last_login is not None


def test_save_with_update_fields_touching_email_revalidates(user: object) -> None:
    user.email = None
    user.phone = None
    with pytest.raises(ValidationError):
        user.save(update_fields=["email", "phone"])
