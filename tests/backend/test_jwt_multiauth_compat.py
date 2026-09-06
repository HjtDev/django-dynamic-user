"""Proves this package's v1.1.0 identity change actually satisfies
``../django-jwt-multiauth``'s frozen ``UserProvisioningService.get_or_create`` contract
(``docs/CONTRACT.md`` §1, jwt-multiauth's own ``docs/CONTRACT.md`` §4/§11 item 19) — without
depending on that package (a declared-dependency violation), by replaying its documented
built-in algorithm verbatim against this app's real, resolved user model:

    sets the named field (``phone``/``email``) to ``identifier``, sets the model's
    ``USERNAME_FIELD`` too if it's a different, still-empty field, calls
    ``set_unusable_password()``, then ``.save()`` — never ``UserManager.create_user``, never
    ``full_clean()``.

If this suite ever fails, ``dynamic_user`` has regressed the one guarantee the sibling package's
own contract was frozen against.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from dynamic_user import resolution, signals

pytestmark = pytest.mark.django_db


def _provision(*, identifier: str, field: str) -> object:
    """Replays UserProvisioningService.get_or_create's built-in (no PROVISION_CALLBACK) path."""
    model = get_user_model()
    user = model()
    setattr(user, field, identifier)
    if user.USERNAME_FIELD != field and not getattr(user, user.USERNAME_FIELD):
        setattr(user, user.USERNAME_FIELD, identifier)
    user.set_unusable_password()
    user.save()
    return user


def test_phone_provisioning_creates_a_real_user() -> None:
    user = _provision(identifier="+15551234567", field="phone")
    assert user.pk is not None
    assert user.phone == "+15551234567"
    assert user.email is None
    assert user.has_usable_password() is False


def test_email_provisioning_creates_a_real_user() -> None:
    user = _provision(identifier="otp@example.com", field="email")
    assert user.pk is not None
    assert user.email == "otp@example.com"
    assert user.phone is None


def test_required_fields_is_empty_so_e007_could_never_fire() -> None:
    """jwt_multiauth.E007 (its own §11 item 19) rejects a REQUIRED_FIELDS entry the built-in
    provisioning path can't fill. This app's REQUIRED_FIELDS is now [] — there is nothing left
    for that check to ever object to."""
    assert get_user_model().REQUIRED_FIELDS == []


def test_username_field_is_filled_only_when_different_and_still_empty() -> None:
    """USERNAME_FIELD ("username") differs from "phone" and starts empty — the provisioning
    algorithm fills it with the identifier itself, exactly as jwt-multiauth's contract specifies,
    which is also what makes AbstractDynamicUser.save()'s own _ensure_username() a no-op here
    (username was never missing by the time save() runs)."""
    user = _provision(identifier="+15559998888", field="phone")
    assert user.username == "+15559998888"


def test_provisioning_auto_creates_profile_and_setting_with_no_cross_app_wiring() -> None:
    """The entire point of connecting auto-provisioning to post_save with a lazy string sender
    (signals.py) — it fires for ANY creation path, including one this package's own code never
    calls, with zero changes needed on either side of the package boundary."""
    user = _provision(identifier="+15550001111", field="phone")

    profile_model = resolution.get_profile_model()
    setting_model = resolution.get_setting_model()
    assert profile_model.objects.filter(user=user).exists()
    assert setting_model.objects.filter(user=user).exists()


def test_provisioning_fires_profile_created_and_setting_created_exactly_once() -> None:
    received: list[tuple[str, dict]] = []

    def _make(name: str):
        def _receiver(sender, **kwargs) -> None:
            received.append((name, kwargs))

        return _receiver

    receivers = {name: _make(name) for name in ("profile_created", "setting_created")}
    for name, receiver in receivers.items():
        getattr(signals, name).connect(receiver)
    try:
        user = _provision(identifier="+15552223333", field="phone")
    finally:
        for name, receiver in receivers.items():
            getattr(signals, name).disconnect(receiver)

    names = [name for name, _ in received]
    assert names.count("profile_created") == 1
    assert names.count("setting_created") == 1
    for _, kwargs in received:
        assert kwargs["user_id"] == user.pk


def test_provisioning_fires_user_created_after_profile_and_setting_provisioning() -> None:
    """user_created is connected last in apps.py's ready() specifically so a receiver can rely
    on Profile/Setting already existing by the time it fires — proven here, not just documented."""
    seen_profile_exists_at_user_created_time = []

    def _on_user_created(sender, user_id, **kwargs) -> None:
        profile_model = resolution.get_profile_model()
        setting_model = resolution.get_setting_model()
        seen_profile_exists_at_user_created_time.append(
            profile_model.objects.filter(user_id=user_id).exists()
            and setting_model.objects.filter(user_id=user_id).exists()
        )

    signals.user_created.connect(_on_user_created)
    try:
        _provision(identifier="+15554445555", field="phone")
    finally:
        signals.user_created.disconnect(_on_user_created)

    assert seen_profile_exists_at_user_created_time == [True]


def test_create_superuser_with_no_email_but_a_phone_works() -> None:
    """jwt-multiauth's own generic test fixtures create a superuser with no email at all
    (against whatever user model a given settings leg configures) — for THIS package's concrete
    model that still must supply a phone, since REQUIRED_FIELDS no longer demanding email does
    not waive the email-or-phone rule itself (a superuser with neither is correctly rejected,
    same as any other user — see test_identity.py)."""
    user = get_user_model().objects.create_superuser(
        username="admin2", phone="+15556667777", password="pw"
    )
    assert user.is_superuser is True
    assert user.email is None
