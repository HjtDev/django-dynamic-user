"""Self-service URLconf, basePath ``/api/v1/users``.

``docs/CONTRACT.md`` §5's self-service routes — own info, edit own profile/setting, browse
others' public profiles, request/cancel account deletion. A host mounts this module under its own
API namespace; ``urls_admin.py`` (admin-only, Phase 6) is mounted separately, under a different
namespace/permission tier entirely.
"""

from __future__ import annotations

from django.urls import URLPattern, path

from dynamic_user.views import (
    MeView,
    MyDeletionRequestView,
    MyProfileView,
    MySettingView,
    PublicProfileDetailView,
    PublicProfileListView,
)

urlpatterns: list[URLPattern] = [
    path("me/", MeView.as_view(), name="dynamic-user-me"),
    path("me/profile/", MyProfileView.as_view(), name="dynamic-user-my-profile"),
    path("me/setting/", MySettingView.as_view(), name="dynamic-user-my-setting"),
    path(
        "me/deletion-request/",
        MyDeletionRequestView.as_view(),
        name="dynamic-user-my-deletion-request",
    ),
    path("profiles/", PublicProfileListView.as_view(), name="dynamic-user-profile-list"),
    path(
        "profiles/<int:id>/", PublicProfileDetailView.as_view(), name="dynamic-user-profile-detail"
    ),
]
