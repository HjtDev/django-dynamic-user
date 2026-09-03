"""The settings-driven serializer factory — so a host's subclassed model needs zero view-layer
changes.

Phase 4 implements ``build_serializer()``, resolving field allowlists from ``conf.py`` against
the *resolved* model (``resolution.py``, never a hardcoded default) at call time — never baked
into a model's class attributes or ``Meta`` (this repo's ``CLAUDE.md`` rule 2: a settings change
must never produce a migration diff). Raises ``django.core.exceptions.ImproperlyConfigured`` if
called before ``checks.py``'s ``dynamic_user.E005`` allowlist check has had a chance to run
(``docs/CONTRACT.md`` §6), naming the offending field and setting key.

``password`` is excluded from every serializer this factory can produce or accept,
unconditionally — a hard deny-list, never a per-call opt-out (``docs/CONTRACT.md`` §5, this
repo's ``CLAUDE.md`` rule 3: no serializer, on either surface, ever emits ``password`` or a
hash).
"""
