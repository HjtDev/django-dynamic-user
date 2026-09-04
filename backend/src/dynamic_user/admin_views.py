"""The admin DRF API — full read/write over every user, gated by ``IsDynamicUserAdmin``.

Phase 6 implements the views backing ``urls_admin.py``'s routes (basePath
``/api/v1/admin/users``), including the account-deletion review flow (``DeletionService.review``/
``finalize``). Paired with ``urls_admin.py``, the way ``views.py`` pairs with ``urls.py``.

**Not** ``views_admin.py`` — Phase 1 stubbed both a ``views_admin.py`` (DRF admin API) and this
module (docstring described as Jazzmin HTML dashboard pages), splitting the two surfaces
"Admin API and Jazzmin admin" names across two files. ``docs/APP-DESIGN.md`` §5, ``cleanup_app``'s
own layout, and this app's own Phase 6 guide prompt all name *this* module — ``admin_views.py`` —
as the DRF admin API; the contract specifies no custom Jazzmin HTML page at all. ``views_admin.py``
was therefore deleted as dead weight (``docs/CONTRACT.md`` §10 deviation).

Any write touching ``conf.get_privileged_fields()`` — ``is_staff``/``is_superuser``/
``is_active``/``groups``/``user_permissions`` — passes through ``CanEscalatePrivilege`` with
zero exceptions, independent of ``DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]`` (this repo's
``CLAUDE.md`` rule 5). ``POST /deletion-requests/{id}/finalize/`` passes through ``IsSuperUser``
unconditionally, for the same reason.
"""

from __future__ import annotations

from typing import Any, cast

from appkit.pagination import DefaultPagination
from appkit.validation import safe_filter_kwargs, validate_query_params
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from dynamic_user import resolution, serializers
from dynamic_user.models import AccountDeletionRequest
from dynamic_user.permissions import CanEscalatePrivilege, IsDynamicUserAdmin, IsSuperUser
from dynamic_user.serializers import (
    AdminDeletionRequestFilterSerializer,
    AdminDeletionRequestSerializer,
    AdminUserFilterSerializer,
    DeletionReviewSerializer,
)
from dynamic_user.services import (
    DeletionService,
    InvalidDeletionState,
    ProfileService,
    SettingService,
)
from dynamic_user.views import DeletionRequestConflict

__all__ = [
    "AdminDeletionRequestFinalizeView",
    "AdminDeletionRequestListView",
    "AdminDeletionRequestReviewView",
    "AdminUserDetailView",
    "AdminUserListView",
    "AdminUserProfileView",
    "AdminUserSettingView",
]


def _filterable_user_fields(model: type[Any]) -> frozenset[str]:
    """Field names ``AdminUserListView`` accepts as a query-param filter, derived from the
    *resolved* user model at request time rather than a static list — the same reasoning
    ``serializers._valid_field_names`` documents. Excludes relations (``groups``,
    ``user_permissions``, reverse accessors) — an ``exact`` lookup against a raw query string
    isn't a shape those support, and excluding them keeps them out of a filter surface
    entirely, on top of already being gated as write targets by ``CanEscalatePrivilege``.
    Excludes :data:`serializers.DENIED_FIELDS` — ``password`` is never filterable either."""
    return frozenset(
        f.name
        for f in model._meta.get_fields()
        if getattr(f, "concrete", False)
        and not getattr(f, "is_relation", False)
        and f.name not in serializers.DENIED_FIELDS
    )


@extend_schema_view(
    get=extend_schema(
        summary="List users (admin)",
        description=(
            "Paginated, filterable list of every user. USER_READ_FIELDS-shaped full fields "
            "except password. Beyond page/page_size, any concrete, non-relation field on the "
            "resolved user model is accepted as an exact-match query filter (?field=value) — "
            "see _filterable_user_fields(). That set is host-dependent (a subclassed User model "
            "adds its own fields), so it cannot be enumerated as fixed OpenAPI parameters here; "
            "the frontend SDK's AdminUsersParams type is intentionally open-ended for the same "
            "reason."
        ),
        responses=serializers.get_admin_user_serializer(),
        tags=["dynamic-user-admin"],
    )
)
class AdminUserListView(generics.ListAPIView[Any]):
    """``GET /``. Filters via ``appkit.validation.validate_query_params`` +
    ``safe_filter_kwargs`` against :func:`_filterable_user_fields` — never raw ``**request.GET``
    into ``filter()``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_users_list"
    pagination_class = DefaultPagination

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_admin_user_serializer()

    def get_queryset(self) -> Any:
        model = get_user_model()
        validate_query_params(AdminUserFilterSerializer, self.request.query_params)
        filter_kwargs = safe_filter_kwargs(
            self.request.query_params, allowed_fields=_filterable_user_fields(model)
        )
        # Explicit ordering: pagination over an unordered queryset triggers Django's own
        # UnorderedObjectListWarning and can silently reorder between pages.
        return cast(Any, model)._default_manager.filter(**filter_kwargs).order_by("pk")


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a user (admin)",
        description="Every real field except password.",
        responses=serializers.get_admin_user_serializer(),
        tags=["dynamic-user-admin"],
    ),
    patch=extend_schema(
        summary="Update a user (admin)",
        description=(
            "Any user field except password. 403 (whole request rejected) if a non-superuser's "
            "body touches is_staff/is_superuser/is_active/groups/user_permissions."
        ),
        request=serializers.get_admin_user_serializer(),
        responses=serializers.get_admin_user_serializer(),
        tags=["dynamic-user-admin"],
    ),
)
class AdminUserDetailView(generics.RetrieveUpdateAPIView[Any]):
    """``GET``/``PATCH`` ``/{id}/``. ``PUT`` is deliberately unavailable, same reasoning as
    ``MyProfileView`` — ``docs/CONTRACT.md`` §5 lists no full-replace route here either.
    ``CanEscalatePrivilege`` runs ahead of the view touching any field (DRF's ``initial()`` calls
    every permission's ``has_permission`` before the handler)."""

    permission_classes = [  # noqa: RUF012
        IsAuthenticated,
        IsDynamicUserAdmin,
        CanEscalatePrivilege,
    ]
    http_method_names = ["get", "patch", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_user_retrieve"
    lookup_field = "pk"
    lookup_url_kwarg = "id"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_admin_user_serializer()

    def get_queryset(self) -> Any:
        return cast(Any, get_user_model())._default_manager.all()

    def get_throttles(self) -> list[Any]:
        if self.request.method == "PATCH":
            self.throttle_scope = "dynamic_user_admin_user_update"
        return super().get_throttles()


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a user's profile (admin)",
        description="Every real field on the resolved Profile model.",
        responses=serializers.get_admin_profile_serializer(),
        tags=["dynamic-user-admin"],
    ),
    patch=extend_schema(
        summary="Update a user's profile (admin)",
        description="Any Profile field, applied via ProfileService.update.",
        request=serializers.get_admin_profile_serializer(),
        responses=serializers.get_admin_profile_serializer(),
        tags=["dynamic-user-admin"],
    ),
)
class AdminUserProfileView(generics.RetrieveUpdateAPIView[Any]):
    """``GET``/``PATCH`` ``/{id}/profile/`` — the target user is resolved from the URL id, unlike
    ``MyProfileView``'s always-``request.user`` shape; that is the entire point of this surface.
    ``IsProfileOwner`` is deliberately absent — an admin editing someone else's row is exactly
    what this endpoint is for."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    http_method_names = ["get", "patch", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_profile_update"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_admin_profile_serializer()

    def _target_user(self) -> Any:
        model = get_user_model()
        return get_object_or_404(cast(Any, model)._default_manager.all(), pk=self.kwargs["id"])

    def get_object(self) -> Any:
        target_user = self._target_user()
        model = resolution.get_profile_model()
        profile, _ = cast(Any, model).objects.get_or_create(user=target_user)
        return profile

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        target_user = self._target_user()
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = ProfileService.update(target_user, serializer.validated_data)
        read_serializer = serializers.get_admin_profile_serializer()(updated)
        return Response(read_serializer.data)


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a user's setting (admin)",
        description="Every real field on the resolved Setting model.",
        responses=serializers.get_admin_setting_serializer(),
        tags=["dynamic-user-admin"],
    ),
    patch=extend_schema(
        summary="Update a user's setting (admin)",
        description="Any Setting field, applied via SettingService.update.",
        request=serializers.get_admin_setting_serializer(),
        responses=serializers.get_admin_setting_serializer(),
        tags=["dynamic-user-admin"],
    ),
)
class AdminUserSettingView(generics.RetrieveUpdateAPIView[Any]):
    """``GET``/``PATCH`` ``/{id}/setting/`` — same shape as :class:`AdminUserProfileView`, over
    ``SettingService`` instead of ``ProfileService``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    http_method_names = ["get", "patch", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_setting_update"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_admin_setting_serializer()

    def _target_user(self) -> Any:
        model = get_user_model()
        return get_object_or_404(cast(Any, model)._default_manager.all(), pk=self.kwargs["id"])

    def get_object(self) -> Any:
        target_user = self._target_user()
        model = resolution.get_setting_model()
        setting, _ = cast(Any, model).objects.get_or_create(user=target_user)
        return setting

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        target_user = self._target_user()
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = SettingService.update(target_user, serializer.validated_data)
        read_serializer = serializers.get_admin_setting_serializer()(updated)
        return Response(read_serializer.data)


@extend_schema_view(
    get=extend_schema(
        summary="List account-deletion requests (admin)",
        description="Paginated, filterable by status.",
        # get_queryset() below reads `status` (validated by AdminDeletionRequestFilterSerializer)
        # but it's not a DRF filter_backend/pagination param drf-spectacular can infer on its
        # own — undeclared here, it would silently vanish from schema.yml and therefore from the
        # frontend SDK's generated AdminDeletionRequestsParams type.
        parameters=[
            OpenApiParameter(
                "status",
                str,
                OpenApiParameter.QUERY,
                required=False,
                enum=AccountDeletionRequest.Status.values,
                description="Filter by status.",
            ),
        ],
        responses=AdminDeletionRequestSerializer,
        tags=["dynamic-user-admin"],
    )
)
class AdminDeletionRequestListView(generics.ListAPIView[Any]):
    """``GET /deletion-requests/``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_deletions_list"
    pagination_class = DefaultPagination
    serializer_class = AdminDeletionRequestSerializer

    def get_queryset(self) -> Any:
        query = validate_query_params(
            AdminDeletionRequestFilterSerializer, self.request.query_params
        )
        queryset = AccountDeletionRequest.objects.select_related("user", "reviewed_by").order_by(
            "-requested_at"
        )
        status_filter = query.validated_data.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class AdminDeletionRequestReviewView(APIView):
    """``POST /deletion-requests/{id}/review/``. Calls ``DeletionService.review`` — never
    touches the model layer itself."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_deletion_review"

    @extend_schema(
        summary="Review an account-deletion request (admin)",
        description="Moves a PENDING request to APPROVED or REJECTED. 409 if not PENDING.",
        request=DeletionReviewSerializer,
        responses={200: AdminDeletionRequestSerializer},
        tags=["dynamic-user-admin"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = DeletionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            deletion_request = DeletionService.review(
                kwargs["id"],
                approved=serializer.validated_data["approved"],
                reviewed_by=cast(Any, request.user),
            )
        except InvalidDeletionState as exc:
            raise DeletionRequestConflict(str(exc)) from exc
        return Response(AdminDeletionRequestSerializer(deletion_request).data)


class AdminDeletionRequestFinalizeView(APIView):
    """``POST /deletion-requests/{id}/finalize/``. Calls ``DeletionService.finalize`` early,
    bypassing ``finalize_at`` — superuser-only, always, regardless of
    ``ADMIN_REQUIRES_SUPERUSER`` (``docs/CONTRACT.md`` §5)."""

    permission_classes = [IsAuthenticated, IsSuperUser]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_deletion_finalize"

    @extend_schema(
        summary="Finalize an account-deletion request early (admin, superuser-only)",
        description=(
            "Bypasses finalize_at. Irreversible. 409 if the request isn't currently APPROVED."
        ),
        # No request body — explicit `request=None` is required here (unlike DELETE, which
        # drf-spectacular already assumes carries none): a bare APIView.post() with no
        # serializer_class and no `request=` makes AutoSchema try to guess one and fail.
        request=None,
        responses={204: None},
        tags=["dynamic-user-admin"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            DeletionService.finalize(kwargs["id"])
        except InvalidDeletionState as exc:
            raise DeletionRequestConflict(str(exc)) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)
