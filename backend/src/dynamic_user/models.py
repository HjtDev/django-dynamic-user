"""Data models: ``AbstractDynamicUser``/``User``, ``AbstractProfile``/``Profile``,
``AbstractSetting``/``Setting``, and ``AccountDeletionRequest``.

Phase 2 implements all four exactly as ``docs/CONTRACT.md`` §1 specifies — abstract bases so a
host can subclass any of the three swappable models, plus a concrete default the host can also
install as-is. Every model in this module declares ``Meta.indexes`` for fields used in frequent
filters, ordering, or foreign key lookups (``APP-DESIGN.md`` §2's baseline query-optimization
note).

Every FK-shaped reference anywhere in this module is ``settings.AUTH_USER_MODEL`` — never a
concrete ``User`` import, and never a reference to another app package's model
(``docs/CONTRACT.md`` §1: "Requires another app package: No").

``AbstractProfile``/``AbstractSetting`` are also what ``checks.py``'s Phase-2-reserved
``dynamic_user.E004`` validates a host's swapped model against — see that module's docstring.
"""
