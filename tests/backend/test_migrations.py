"""Asserts the exact shape of ``dynamic_user/migrations/0001_initial.py`` this phase's plan
decided on (``docs/CONTRACT.md`` §10 item 14): ``migrations.swappable_dependency()`` for
``AUTH_USER_MODEL`` only — never for this app's own ``DYNAMIC_USER_PROFILE_MODEL``/
``DYNAMIC_USER_SETTING_MODEL`` settings, which would create a ``CircularDependencyError`` for a
host swapping only Profile/Setting while leaving User at its default (proven for real by
``test_partial_swap.py``, which runs an actual migration against exactly that layout).

Also proves ``Profile``/``Setting``'s own ``CreateModel`` operations carry
``options["swappable"]`` — the mechanism that actually lets ``resolution.py`` point at a swapped
model, since the dependency edge above is not it.
"""

from __future__ import annotations

import importlib

from django.conf import settings
from django.db import migrations


def _load_0001_initial():
    return importlib.import_module("dynamic_user.migrations.0001_initial")


def test_0001_initial_depends_on_auth_user_model_swappable_dependency() -> None:
    module = _load_0001_initial()
    expected = migrations.swappable_dependency(settings.AUTH_USER_MODEL)
    assert expected in module.Migration.dependencies


def test_0001_initial_declares_exactly_one_swappable_dependency() -> None:
    """Under these (default, unswapped) settings, ``swappable_dependency("dynamic_user.User")``
    and a hypothetical ``swappable_dependency("dynamic_user.Profile")`` collapse to the exact
    same ``("dynamic_user", "__first__")`` tuple — they share an app label, and
    ``swappable_dependency()`` only ever encodes the app label, not the specific model name
    (``django/db/migrations/migration.py``'s own ``swappable_dependency()``). So this test can
    only prove "exactly one dependency was added, not three" here; it cannot by itself
    distinguish "the AUTH_USER_MODEL edge" from "an also-added DYNAMIC_USER_PROFILE_MODEL edge"
    under same-app settings. The real, unambiguous proof that no dependency was added for
    DYNAMIC_USER_PROFILE_MODEL/DYNAMIC_USER_SETTING_MODEL is `test_partial_swap.py`: it swaps
    Profile/Setting into a genuinely different app and applies the resulting migration graph
    against real Postgres — which would raise CircularDependencyError at collection time if such
    a dependency existed.
    """
    module = _load_0001_initial()
    swappable_shaped = [
        dep for dep in module.Migration.dependencies if dep == ("dynamic_user", "__first__")
    ]
    assert len(swappable_shaped) == 1


def test_user_create_model_is_swappable_for_auth_user_model() -> None:
    module = _load_0001_initial()
    op = _create_model_op(module, "User")
    assert op.options.get("swappable") == "AUTH_USER_MODEL"


def test_profile_create_model_is_swappable_for_its_own_setting() -> None:
    module = _load_0001_initial()
    op = _create_model_op(module, "Profile")
    assert op.options.get("swappable") == "DYNAMIC_USER_PROFILE_MODEL"


def test_setting_create_model_is_swappable_for_its_own_setting() -> None:
    module = _load_0001_initial()
    op = _create_model_op(module, "Setting")
    assert op.options.get("swappable") == "DYNAMIC_USER_SETTING_MODEL"


def _create_model_op(module, model_name: str):
    for op in module.Migration.operations:
        if isinstance(op, migrations.CreateModel) and op.name == model_name:
            return op
    raise AssertionError(f"No CreateModel operation found for {model_name!r}")
