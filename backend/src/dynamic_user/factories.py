"""``factory_boy`` factories — this app's public *test-only* surface (``APP-DESIGN.md`` §7.3).

Factories for ``User``/``Profile``/``Setting``/``AccountDeletionRequest``. A host's own test
suite is expected to import from here rather than hand-rolling equivalents.

Every model reference is indirect — ``django.contrib.auth.get_user_model()`` for the user,
``dynamic_user.resolution.get_profile_model()``/``get_setting_model()`` for the other two — the
same rule this repo's ``CLAUDE.md`` states for every other module. ``AccountDeletionRequest`` is
imported concretely, since it documents itself as not swappable (``models.py``'s own docstring).
Resolving swappable models at this module's top level (in each factory's ``Meta.model``) is safe
here for the same reason it's safe in ``admin.py``: this module is only ever imported from test
code, after Django's app registry is fully configured — never from ``apps.py``/``models.py``/
anything this package's own runtime import graph touches.

``UserFactory``'s ``phone_only``/``email_only`` traits exist because of this app's v1.1.0 identity
rule (``docs/CONTRACT.md`` §1): at least one of ``email``/``phone`` is required, but neither is
required individually — a phone-OTP or email-OTP registration only ever has one. A plain
``UserFactory()`` call (no trait) still sets both, matching the pre-1.1.0 default shape most
existing host tests already assume.

This module is ruff-banned from ``src/dynamic_user`` (see ``backend/pyproject.toml``'s
``banned-api`` block) — nothing under ``src/`` may import it, since importing test factories
from production code is exactly the mistake that guard exists to catch. The test tree
(``../tests/backend``) is exempted from that ban.
"""

from __future__ import annotations

from typing import Any

import factory.django
from django.contrib.auth import get_user_model
from factory.declarations import Sequence, SubFactory, Trait

from dynamic_user import resolution
from dynamic_user.models import AccountDeletionRequest


class UserFactory(factory.django.DjangoModelFactory[Any]):
    """``Any``, not the abstract ``AbstractDynamicUser`` — a resolved swappable model is always a
    concrete subclass, never the abstract base itself, and django-stubs has no way to express
    "whatever concrete model AUTH_USER_MODEL resolves to" as a static type. Every other factory
    below over a swappable model uses the same parameter for the same reason."""

    class Meta:
        model = get_user_model()
        django_get_or_create = ("username",)

    class Params:
        phone_only = Trait(
            email=None,
            phone=Sequence(lambda n: f"+1555{n:07d}"),
        )
        email_only = Trait(
            phone=None,
        )

    username = Sequence(lambda n: f"user{n}")
    email = Sequence(lambda n: f"user{n}@example.com")


class ProfileFactory(factory.django.DjangoModelFactory[Any]):
    class Meta:
        model = resolution.get_profile_model()
        django_get_or_create = ("user",)

    user = SubFactory(UserFactory)


class SettingFactory(factory.django.DjangoModelFactory[Any]):
    class Meta:
        model = resolution.get_setting_model()
        django_get_or_create = ("user",)

    user = SubFactory(UserFactory)


class AccountDeletionRequestFactory(factory.django.DjangoModelFactory[AccountDeletionRequest]):
    class Meta:
        model = AccountDeletionRequest

    user = SubFactory(UserFactory)
    reason = ""
