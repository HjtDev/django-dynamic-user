"""Admin URLconf, basePath ``/api/v1/admin/users``.

``docs/CONTRACT.md`` §5's admin routes — full read/write over every user, plus the
account-deletion review flow — every one gated by ``IsDynamicUserAdmin``/``CanEscalatePrivilege``/
``IsSuperUser`` from ``permissions.py``. A host mounts this module separately from ``urls.py``
(self-service), under its own admin API namespace.

Paths collapse to the basePath root — ``/api/v1/admin/users/42/``, not
``.../users/users/42/`` (``docs/CONTRACT.md`` §10 item 7). Every named segment
(``deletion-requests/``, ``profiles/``, ``settings/``, ``change-log/``, ``log-entries/``,
``groups/``, ``permissions/``) stays ahead of ``<int:id>/`` in ``urlpatterns`` so it can never
collide with an integer user id.

``log-entries/`` (v1.1.0) is wired only when ``django.contrib.admin`` is installed — Django's own
``LogEntry`` model has no meaningful data without it. Checked once, at URLconf-import time
(``django.apps.apps.is_installed``), the same way ``admin_views.py`` guards the views themselves.
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.urls import URLPattern, path

from dynamic_user.admin_views import (
    AdminChangeLogDetailView,
    AdminChangeLogListView,
    AdminDeletionRequestDetailView,
    AdminDeletionRequestFinalizeView,
    AdminDeletionRequestListView,
    AdminDeletionRequestReviewView,
    AdminGroupDetailView,
    AdminGroupListView,
    AdminPermissionListView,
    AdminProfileDetailView,
    AdminProfileListView,
    AdminSettingDetailView,
    AdminSettingListView,
    AdminUserDetailView,
    AdminUserListView,
    AdminUserProfileView,
    AdminUserSetPasswordView,
    AdminUserSettingView,
)

urlpatterns: list[URLPattern] = [
    path(
        # v1.1.0: GET lists, POST creates — same URL, same view (AdminDeletionRequestListView is
        # a ListCreateAPIView), the same shape as every other admin collection in this file.
        "deletion-requests/",
        AdminDeletionRequestListView.as_view(),
        name="dynamic-user-admin-deletion-request-list",
    ),
    path(
        "deletion-requests/<int:id>/",
        AdminDeletionRequestDetailView.as_view(),
        name="dynamic-user-admin-deletion-request-detail",
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
    path(
        "profiles/",
        AdminProfileListView.as_view(),
        name="dynamic-user-admin-profile-list",
    ),
    path(
        "profiles/<int:profile_id>/",
        AdminProfileDetailView.as_view(),
        name="dynamic-user-admin-profile-detail",
    ),
    path(
        "settings/",
        AdminSettingListView.as_view(),
        name="dynamic-user-admin-setting-list",
    ),
    path(
        "settings/<int:setting_id>/",
        AdminSettingDetailView.as_view(),
        name="dynamic-user-admin-setting-detail",
    ),
    path(
        "change-log/",
        AdminChangeLogListView.as_view(),
        name="dynamic-user-admin-change-log-list",
    ),
    path(
        "change-log/<int:id>/",
        AdminChangeLogDetailView.as_view(),
        name="dynamic-user-admin-change-log-detail",
    ),
    path("groups/", AdminGroupListView.as_view(), name="dynamic-user-admin-group-list"),
    path(
        "groups/<int:id>/", AdminGroupDetailView.as_view(), name="dynamic-user-admin-group-detail"
    ),
    path(
        "permissions/",
        AdminPermissionListView.as_view(),
        name="dynamic-user-admin-permission-list",
    ),
    path("", AdminUserListView.as_view(), name="dynamic-user-admin-user-list"),
    path("<int:id>/", AdminUserDetailView.as_view(), name="dynamic-user-admin-user-detail"),
    path(
        "<int:id>/set-password/",
        AdminUserSetPasswordView.as_view(),
        name="dynamic-user-admin-user-set-password",
    ),
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

if django_apps.is_installed("django.contrib.admin"):
    from dynamic_user.admin_views import AdminLogEntryDetailView, AdminLogEntryListView

    urlpatterns = [
        path(
            "log-entries/",
            AdminLogEntryListView.as_view(),
            name="dynamic-user-admin-log-entry-list",
        ),
        path(
            "log-entries/<int:id>/",
            AdminLogEntryDetailView.as_view(),
            name="dynamic-user-admin-log-entry-detail",
        ),
        *urlpatterns,
    ]
