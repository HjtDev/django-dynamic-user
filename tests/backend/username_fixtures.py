"""Dotted-path ``USERNAME_GENERATOR`` targets for ``test_identity.py`` — a real, importable
module so :func:`dynamic_user.usernames.generate_username` can resolve a genuine dotted path
rather than mocking ``import_string`` itself. Mirrors ``validator_fixtures.py``'s own shape.
"""

from __future__ import annotations

from typing import Any

_counter = 0


def custom_username_generator(model: type[Any]) -> str:
    """A trivially distinct, deterministic-enough generator — proves ``USERNAME_GENERATOR`` is
    genuinely resolved and called, not silently ignored."""
    global _counter
    _counter += 1
    return f"custom-{_counter}"


#: Not callable — used to prove generate_username fails closed on a resolvable-but-non-callable
#: dotted path, not just an unimportable one.
NOT_CALLABLE = "just a string"
