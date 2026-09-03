"""Dotted-path validator targets for ``test_validators.py`` — a real, importable module so
``run_validators`` can resolve genuine dotted paths rather than mocking ``import_string`` itself.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError


def always_pass(value: Any) -> None:
    pass


def always_fail(value: Any) -> None:
    raise ValidationError("always_fail rejected this value")


#: Not callable — used to prove run_validators fails closed on a resolvable-but-non-callable
#: dotted path, not just an unimportable one.
NOT_CALLABLE = "just a string"
