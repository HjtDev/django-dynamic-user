"""Admin URLconf, basePath ``/api/v1/admin/users``.

Phase 6 adds ``docs/CONTRACT.md`` §5's admin routes here — full read/write over every user, plus
the account-deletion review flow — every one gated by ``IsDynamicUserAdmin``/
``CanEscalatePrivilege`` from ``permissions.py``. A host mounts this module separately from
``urls.py`` (self-service), under its own admin API namespace.
"""

from __future__ import annotations

from django.urls import URLPattern

urlpatterns: list[URLPattern] = []
