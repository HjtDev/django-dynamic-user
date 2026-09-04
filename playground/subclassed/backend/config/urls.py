"""Subclassed-host playground URLconf. Same mounting as ../../default/backend/config/urls.py —
proving the URL surface needs zero changes for a host that has subclassed all three models.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def healthz(request):  # noqa: ANN001, ANN201 -- playground-only, not part of the app's contract
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/users/", include("dynamic_user.urls")),
    path("api/v1/admin/users/", include("dynamic_user.urls_admin")),
    path("healthz/", healthz),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
]
