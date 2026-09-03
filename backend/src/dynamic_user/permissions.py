"""User-facing and admin DRF permission classes.

Phase 5 implements ``IsProfileOwner``, ``IsPublicOrOwner``, ``IsDynamicUserAdmin`` (``is_staff``
by default, tightened to ``is_superuser`` when ``DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]`` is
``True``), and ``CanEscalatePrivilege`` — the one permission class every write path touching
``conf.get_privileged_fields()`` must pass through, gated on an actual superuser with zero
exceptions regardless of ``ADMIN_REQUIRES_SUPERUSER`` (this repo's ``CLAUDE.md`` rule 5:
independent of that switch, and never relaxed by it, only an actual superuser may write
``is_staff``/``is_superuser``/``is_active`` on anyone).
"""
