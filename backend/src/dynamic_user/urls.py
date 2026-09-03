"""Self-service URLconf, basePath ``/api/v1/users``.

Phase 5 adds ``docs/CONTRACT.md`` §5's self-service routes here — own info, edit own
profile/setting, browse others' public profiles. A host mounts this module under its own
API namespace; ``urls_admin.py`` (admin-only) is mounted separately, under a different
namespace/permission tier entirely.
"""

from __future__ import annotations

from django.urls import URLPattern

urlpatterns: list[URLPattern] = []
