"""A dotted-path anonymize target for ``test_services.py``'s ``DELETION_MODE="anonymize"``
tests — a real, importable module so ``DeletionService.finalize()`` resolves a genuine dotted
path via ``import_string`` rather than mocking it.
"""

from __future__ import annotations

from typing import Any

#: Records every user this was called with, in order — cleared by a test's own fixture, not
#: automatically, since two different tests exercise it in the same process.
calls: list[Any] = []


def anonymize_user(user: Any) -> None:
    calls.append(user)


#: Not callable — used to prove finalize() fails closed on a resolvable-but-non-callable dotted
#: path the same way validators.run_validators does, not just an unimportable one.
NOT_CALLABLE = "just a string"
