"""Exists so the app's schema can be generated standalone, without a host, and so Django's admin
autodiscovery has a real ``/admin/`` to mount (``test_admin.py`` exercises the registered
``ModelAdmin``s through the real Django admin, not by calling view functions directly).

Mounts ``dynamic_user.urls`` the way a host's own ``backend/config/urls.py`` would per the README
(``docs/APP-DESIGN.md`` §7.1), at the documented basePath ``/api/v1/users/``, and
``dynamic_user.urls_admin`` the same way, under ``/api/v1/admin/users/``.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/users/", include("dynamic_user.urls")),
    path("api/v1/admin/users/", include("dynamic_user.urls_admin")),
]
