"""Admin URLconf, basePath ``/api/v1/admin/users``.

``docs/CONTRACT.md`` §5's admin routes — full read/write over every user, plus the
account-deletion review flow — every one gated by ``IsDynamicUserAdmin``/``CanEscalatePrivilege``/
``IsSuperUser`` from ``permissions.py``. A host mounts this module separately from ``urls.py``
(self-service), under its own admin API namespace.

Paths collapse to the basePath root — ``/api/v1/admin/users/42/``, not
``.../users/users/42/`` (``docs/CONTRACT.md`` §10 item 7). ``deletion-requests/`` stays a named
segment so it can never collide with an integer user id.
"""

from __future__ import annotations

from django.urls import URLPattern, path

from dynamic_user.admin_views import (
    AdminDeletionRequestFinalizeView,
    AdminDeletionRequestListView,
    AdminDeletionRequestReviewView,
    AdminUserDetailView,
    AdminUserListView,
    AdminUserProfileView,
    AdminUserSettingView,
)

urlpatterns: list[URLPattern] = [
    path(
        "deletion-requests/",
        AdminDeletionRequestListView.as_view(),
        name="dynamic-user-admin-deletion-request-list",
    ),
    path(
        "deletion-requests/<int:id>/review/",
        AdminDeletionRequestReviewView.as_view(),
        name="dynamic-user-admin-deletion-request-review",
    ),
    path(
        "deletion-requests/<int:id>/finalize/",
        AdminDeletionRequestFinalizeView.as_view(),
        name="dynamic-user-admin-deletion-request-finalize",
    ),
    path("", AdminUserListView.as_view(), name="dynamic-user-admin-user-list"),
    path("<int:id>/", AdminUserDetailView.as_view(), name="dynamic-user-admin-user-detail"),
    path(
        "<int:id>/profile/",
        AdminUserProfileView.as_view(),
        name="dynamic-user-admin-user-profile",
    ),
    path(
        "<int:id>/setting/",
        AdminUserSettingView.as_view(),
        name="dynamic-user-admin-user-setting",
    ),
]
