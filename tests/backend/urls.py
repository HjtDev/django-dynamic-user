"""Exists so the app's schema can be generated standalone, without a host, and so Django's admin
autodiscovery has a real ``/admin/`` to mount (``test_admin.py`` exercises the registered
``ModelAdmin``s through the real Django admin, not by calling view functions directly).

Phase 5/6 will mount ``dynamic_user.urls``/``dynamic_user.urls_admin`` here the way a host's own
``backend/config/urls.py`` would per the README (``docs/APP-DESIGN.md`` §7.1) — both still ship
empty ``urlpatterns`` as of Phase 2, so there is nothing of this package's own to include yet.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
