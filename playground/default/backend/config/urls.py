"""Default-host playground URLconf. Mounts dynamic_user's self-service API under
``/api/v1/users/`` and its admin API under ``/api/v1/admin/users/`` — matching the two basePath
keys (``dynamic_user`` -> ``/api/v1/users``, ``dynamic_user_admin`` -> ``/api/v1/admin/users``)
``frontend/src/api/config.ts`` defaults to, and that ``app/providers.tsx`` here wires explicitly.

``django.contrib.auth.urls`` provides ``/accounts/login/`` etc. — this app does no authentication
of its own (``CLAUDE.md`` rule: "This app does not do authentication"), so the playground's own
login is plain Django, proxied same-origin through Next's own ``rewrites()``.
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
    # django.views.static.serve() directly, not conf.urls.static.static() (a DEBUG-only no-op) —
    # this playground runs under uvicorn, not runserver's auto-serving dev mode.
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
]
