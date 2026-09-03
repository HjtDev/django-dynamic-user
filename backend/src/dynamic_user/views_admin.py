"""The admin DRF API — full read/write over every user, gated by ``IsDynamicUserAdmin``.

Phase 6 implements the views backing ``urls_admin.py``'s routes (basePath
``/api/v1/admin/users``), including the account-deletion review flow (``DeletionService.review``/
``finalize``). Paired with ``urls_admin.py``, the way ``views.py`` pairs with ``urls.py`` — this
module is the DRF admin surface specifically, distinct from ``admin_views.py``'s Jazzmin
dashboard views (both exist because Phase 6 is titled "Admin API *and* Jazzmin admin": two
distinct surfaces, not one file each accidentally covering the same ground).

Any write touching ``conf.get_privileged_fields()`` — ``is_staff``/``is_superuser``/
``is_active``/``groups``/``user_permissions`` — passes through ``CanEscalatePrivilege`` with
zero exceptions, independent of ``DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]`` (this repo's
``CLAUDE.md`` rule 5).
"""
