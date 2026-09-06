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
from django.apps import apps as django_apps
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from dynamic_user import resolution, serializers
from dynamic_user.audit import log_admin_action
from dynamic_user.models import AccountDeletionRequest, ChangeLogEntry
from dynamic_user.permissions import CanEscalatePrivilege, IsDynamicUserAdmin, IsSuperUser
from dynamic_user.serializers import (
    AdminChangeLogEntrySerializer,
    AdminChangeLogFilterSerializer,
    AdminDeletionRequestFilterSerializer,
    AdminDeletionRequestSerializer,
    AdminGroupSerializer,
    AdminPermissionSerializer,
    AdminProfileFilterSerializer,
    AdminSetPasswordSerializer,
    AdminSettingFilterSerializer,
    AdminUserFilterSerializer,
    DeletionReviewSerializer,
)
from dynamic_user.services import (
    DeletionRequestAlreadyExists,
    DeletionService,
    InvalidDeletionState,
    ProfileService,
    SettingService,
    UserService,
)
from dynamic_user.views import DeletionRequestConflict, reraise_as_drf_validation_error

__all__ = [
    "AdminChangeLogDetailView",
    "AdminChangeLogListView",
    "AdminDeletionRequestDetailView",
    "AdminDeletionRequestFinalizeView",
    "AdminDeletionRequestListView",
    "AdminDeletionRequestReviewView",
    "AdminGroupDetailView",
    "AdminGroupListView",
    "AdminPermissionListView",
    "AdminProfileDetailView",
    "AdminProfileListView",
    "AdminSettingDetailView",
    "AdminSettingListView",
    "AdminUserDetailView",
    "AdminUserListView",
    "AdminUserProfileView",
    "AdminUserSetPasswordView",
    "AdminUserSettingView",
]

if django_apps.is_installed("django.contrib.admin"):
    __all__ += ["AdminLogEntryDetailView", "AdminLogEntryListView"]


def _filterable_user_fields(model: type[Any]) -> frozenset[str]:
    """Field names ``AdminUserListView`` accepts as a query-param filter, derived from the
    *resolved* user model at request time rather than a static list — the same reasoning
    ``serializers._valid_field_names`` documents. Excludes relations (``groups``,
    ``user_permissions``, reverse accessors) — an ``exact`` lookup against a raw query string
    isn't a shape those support, and excluding them keeps them out of a filter surface
    entirely, on top of already being gated as write targets by ``CanEscalatePrivilege``.
    Excludes :data:`serializers.DENIED_FIELDS` — ``password`` is never filterable either."""
    return _filterable_model_fields(model) - serializers.DENIED_FIELDS


def _filterable_model_fields(model: type[Any]) -> frozenset[str]:
    """v1.1.0. The generic form behind :func:`_filterable_user_fields` — every concrete,
    non-relation field on ``model``, derived at request time. Used directly (with no
    ``DENIED_FIELDS`` subtraction — neither Profile nor Setting has a ``password`` field) by
    :class:`AdminProfileListView`/:class:`AdminSettingListView`, so a host's subclassed field is
    filterable there with zero package changes too."""
    return frozenset(
        f.name
        for f in model._meta.get_fields()
        if getattr(f, "concrete", False) and not getattr(f, "is_relation", False)
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
    ),
    post=extend_schema(
        summary="Create a user (admin)",
        description=(
            "v1.1.0. Any user field, plus an optional write-only password (unset -> "
            "set_unusable_password()). 403 (whole request rejected) if a non-superuser's body "
            "touches is_staff/is_superuser/is_active/groups/user_permissions — the same "
            "CanEscalatePrivilege gate PATCH /{id}/ already uses."
        ),
        request=serializers.get_admin_user_create_serializer(),
        responses={201: serializers.get_admin_user_serializer()},
        tags=["dynamic-user-admin"],
    ),
)
class AdminUserListView(generics.ListCreateAPIView[Any]):
    """``GET``/``POST`` ``/``. Filters via ``appkit.validation.validate_query_params`` +
    ``safe_filter_kwargs`` against :func:`_filterable_user_fields` — never raw ``**request.GET``
    into ``filter()``. ``POST`` is v1.1.0 — ``CanEscalatePrivilege`` is safe to list unconditionally
    alongside ``GET`` here since it always passes for a safe method (``permissions.py``)."""

    permission_classes = [  # noqa: RUF012
        IsAuthenticated,
        IsDynamicUserAdmin,
        CanEscalatePrivilege,
    ]
    throttle_scope = "dynamic_user_admin_users_list"
    pagination_class = DefaultPagination

    def get_serializer_class(self) -> type[Any]:
        if self.request.method == "POST":
            return serializers.get_admin_user_create_serializer()
        return serializers.get_admin_user_serializer()

    def get_throttles(self) -> list[Any]:
        if self.request.method == "POST":
            self.throttle_scope = "dynamic_user_admin_user_create"
        return super().get_throttles()

    def get_queryset(self) -> Any:
        model = get_user_model()
        validate_query_params(AdminUserFilterSerializer, self.request.query_params)
        filter_kwargs = safe_filter_kwargs(
            self.request.query_params, allowed_fields=_filterable_user_fields(model)
        )
        # Explicit ordering: pagination over an unordered queryset triggers Django's own
        # UnorderedObjectListWarning and can silently reorder between pages.
        return cast(Any, model)._default_manager.filter(**filter_kwargs).order_by("pk")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)
        password = fields.pop("password", None)
        try:
            user = UserService.create(password=password, **fields)
        except DjangoValidationError as exc:
            reraise_as_drf_validation_error(exc)
        log_admin_action(actor=cast(Any, request.user), obj=user, action_flag=ADDITION)
        read_serializer = serializers.get_admin_user_serializer()(user)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


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
    delete=extend_schema(
        summary="Delete a user (admin, superuser-only)",
        description=(
            "v1.1.0. Hard-deletes the user outright, bypassing the account-deletion review flow "
            "entirely. Superuser-only, always, regardless of ADMIN_REQUIRES_SUPERUSER — the same "
            "floor as POST /deletion-requests/{id}/finalize/, for the same reason: irreversible, "
            "and a compromised staff account should never reach it."
        ),
        responses={204: None},
        tags=["dynamic-user-admin"],
    ),
)
class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView[Any]):
    """``GET``/``PATCH``/``DELETE`` ``/{id}/``. ``PUT`` is deliberately unavailable, same
    reasoning as ``MyProfileView`` — ``docs/CONTRACT.md`` §5 lists no full-replace route here
    either. ``CanEscalatePrivilege`` runs ahead of the view touching any field (DRF's
    ``initial()`` calls every permission's ``has_permission`` before the handler). ``DELETE`` is
    v1.1.0, gated additionally by ``IsSuperUser`` via :meth:`get_permissions` —
    ``CanEscalatePrivilege`` alone would not block it, since a bodyless ``DELETE`` touches no
    privileged field."""

    permission_classes = [  # noqa: RUF012
        IsAuthenticated,
        IsDynamicUserAdmin,
        CanEscalatePrivilege,
    ]
    http_method_names = ["get", "patch", "delete", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_user_retrieve"
    lookup_field = "pk"
    lookup_url_kwarg = "id"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_admin_user_serializer()

    def get_queryset(self) -> Any:
        return cast(Any, get_user_model())._default_manager.all()

    def get_permissions(self) -> list[Any]:
        permissions = [permission_class() for permission_class in self.permission_classes]
        if self.request.method == "DELETE":
            permissions.append(IsSuperUser())
        return permissions

    def get_throttles(self) -> list[Any]:
        if self.request.method == "PATCH":
            self.throttle_scope = "dynamic_user_admin_user_update"
        elif self.request.method == "DELETE":
            self.throttle_scope = "dynamic_user_admin_user_delete"
        return super().get_throttles()

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        try:
            updated = UserService.update(
                cast(Any, instance), serializer.validated_data, actor=cast(Any, request.user)
            )
        except DjangoValidationError as exc:
            reraise_as_drf_validation_error(exc)
        log_admin_action(actor=cast(Any, request.user), obj=cast(Any, updated), action_flag=CHANGE)
        read_serializer = serializers.get_admin_user_serializer()(updated)
        return Response(read_serializer.data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        log_admin_action(
            actor=cast(Any, request.user), obj=cast(Any, instance), action_flag=DELETION
        )
        UserService.delete(cast(Any, instance), actor=cast(Any, request.user))
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminUserSetPasswordView(APIView):
    """v1.1.0. ``POST /{id}/set-password/`` — superuser-only, always, regardless of
    ``ADMIN_REQUIRES_SUPERUSER``: setting an arbitrary password directly is the closest thing on
    this surface to a full account takeover, and must never be reachable by a staff-only admin."""

    permission_classes = [IsAuthenticated, IsSuperUser]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_user_set_password"

    @extend_schema(
        summary="Set a user's password (admin, superuser-only)",
        description="Runs AUTH_PASSWORD_VALIDATORS; sends user_password_set.",
        request=AdminSetPasswordSerializer,
        responses={204: None},
        tags=["dynamic-user-admin"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        model = get_user_model()
        target_user = get_object_or_404(cast(Any, model)._default_manager.all(), pk=kwargs["id"])
        serializer = AdminSetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            UserService.set_password(
                target_user, serializer.validated_data["password"], actor=cast(Any, request.user)
            )
        except DjangoValidationError as exc:
            reraise_as_drf_validation_error(exc)
        log_admin_action(actor=cast(Any, request.user), obj=target_user, action_flag=CHANGE)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
    ),
    post=extend_schema(
        summary="Create an account-deletion request (admin)",
        description=(
            "v1.1.0. {user, reason}. 409 if the user already has a pending or approved request."
        ),
        request=serializers.get_admin_deletion_request_create_serializer(),
        responses={201: AdminDeletionRequestSerializer},
        tags=["dynamic-user-admin"],
    ),
)
class AdminDeletionRequestListView(generics.ListCreateAPIView[Any]):
    """``GET``/``POST`` ``/deletion-requests/``. ``POST`` is v1.1.0 — an admin filing a deletion
    request on a user's behalf. Unlike hand-creating one through Django Admin's own change form,
    this route respects the same duplicate guard, ``finalize_at`` computation, and
    ``deletion_requested`` signal every other creation path gets, via ``DeletionService.request``
    — never the model layer directly."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_deletions_list"
    pagination_class = DefaultPagination

    def get_serializer_class(self) -> type[Any]:
        if self.request.method == "POST":
            return serializers.get_admin_deletion_request_create_serializer()
        return AdminDeletionRequestSerializer

    def get_throttles(self) -> list[Any]:
        if self.request.method == "POST":
            self.throttle_scope = "dynamic_user_admin_deletion_request_create"
        return super().get_throttles()

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

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            deletion_request = DeletionService.request(
                serializer.validated_data["user"],
                reason=serializer.validated_data.get("reason", ""),
            )
        except DeletionRequestAlreadyExists as exc:
            raise DeletionRequestConflict(str(exc)) from exc
        log_admin_action(actor=cast(Any, request.user), obj=deletion_request, action_flag=ADDITION)
        return Response(
            AdminDeletionRequestSerializer(deletion_request).data, status=status.HTTP_201_CREATED
        )


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
        log_admin_action(
            actor=cast(Any, request.user),
            obj=deletion_request,
            action_flag=CHANGE,
            message=f"status={deletion_request.status}",
        )
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
        # Captured before finalize(), which may hard_delete the row (and the user row with it) —
        # there is nothing left to log against afterward in that mode.
        deletion_request = get_object_or_404(AccountDeletionRequest, pk=kwargs["id"])
        try:
            DeletionService.finalize(kwargs["id"])
        except InvalidDeletionState as exc:
            raise DeletionRequestConflict(str(exc)) from exc
        log_admin_action(
            actor=cast(Any, request.user),
            obj=deletion_request,
            action_flag=CHANGE,
            message="finalized",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve an account-deletion request (admin)",
        description=(
            "v1.1.0. Backs the frontend SDK's previously-unpopulated deletionRequest(id) key."
        ),
        responses=AdminDeletionRequestSerializer,
        tags=["dynamic-user-admin"],
    ),
    delete=extend_schema(
        summary="Cancel an account-deletion request (admin)",
        description=(
            "v1.1.0. DeletionService.cancel_by_id — a PENDING or APPROVED request only. 409 if "
            "already REJECTED/FINALIZED."
        ),
        responses={204: None},
        tags=["dynamic-user-admin"],
    ),
)
class AdminDeletionRequestDetailView(generics.RetrieveAPIView[Any]):
    """v1.1.0. ``GET``/``DELETE`` ``/deletion-requests/{id}/``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    http_method_names = ["get", "delete", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_deletion_request_detail"
    serializer_class = AdminDeletionRequestSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self) -> Any:
        return AccountDeletionRequest.objects.select_related("user", "reviewed_by")

    def get_throttles(self) -> list[Any]:
        if self.request.method == "DELETE":
            self.throttle_scope = "dynamic_user_admin_deletion_request_cancel"
        return super().get_throttles()

    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        deletion_request = get_object_or_404(AccountDeletionRequest, pk=kwargs["id"])
        try:
            DeletionService.cancel_by_id(kwargs["id"])
        except InvalidDeletionState as exc:
            raise DeletionRequestConflict(str(exc)) from exc
        log_admin_action(
            actor=cast(Any, request.user),
            obj=deletion_request,
            action_flag=DELETION,
            message="cancelled",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------------- profiles / settings


@extend_schema_view(
    get=extend_schema(
        summary="List profiles (admin)",
        description=(
            "v1.1.0. Paginated, filterable collection over every Profile row — unlike "
            "GET /profiles/ on the self-service surface, not restricted to is_public=True. "
            "Any concrete, non-relation field on the resolved Profile model is accepted as an "
            "exact-match query filter, the same _filterable_model_fields() reasoning as the user "
            "list."
        ),
        responses=serializers.get_admin_profile_serializer(),
        tags=["dynamic-user-admin"],
    ),
    post=extend_schema(
        summary="Create a profile (admin)",
        description="v1.1.0. Any Profile field, including user (writable here only).",
        request=serializers.get_admin_profile_create_serializer(),
        responses={201: serializers.get_admin_profile_serializer()},
        tags=["dynamic-user-admin"],
    ),
)
class AdminProfileListView(generics.ListCreateAPIView[Any]):
    """v1.1.0. ``GET``/``POST`` ``/profiles/`` — the admin *collection* Django Admin's own
    ``ProfileAdmin`` changelist already provides, and the API surface didn't (only the
    per-user ``/{id}/profile/`` route existed before this)."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_profiles_list"
    pagination_class = DefaultPagination

    def get_serializer_class(self) -> type[Any]:
        if self.request.method == "POST":
            return serializers.get_admin_profile_create_serializer()
        return serializers.get_admin_profile_serializer()

    def get_throttles(self) -> list[Any]:
        if self.request.method == "POST":
            self.throttle_scope = "dynamic_user_admin_profile_create"
        return super().get_throttles()

    def get_queryset(self) -> Any:
        model = resolution.get_profile_model()
        validate_query_params(AdminProfileFilterSerializer, self.request.query_params)
        filter_kwargs = safe_filter_kwargs(
            self.request.query_params, allowed_fields=_filterable_model_fields(model)
        )
        return (
            cast(Any, model)
            ._default_manager.filter(**filter_kwargs)
            .select_related("user")
            .order_by("pk")
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        log_admin_action(actor=cast(Any, request.user), obj=profile, action_flag=ADDITION)
        read_serializer = serializers.get_admin_profile_serializer()(profile)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a profile (admin)",
        description="v1.1.0. Keyed by the Profile row's own pk, not the owning user's id.",
        responses=serializers.get_admin_profile_serializer(),
        tags=["dynamic-user-admin"],
    ),
    patch=extend_schema(
        summary="Update a profile (admin)",
        description="v1.1.0. Any Profile field, applied via ProfileService.update.",
        request=serializers.get_admin_profile_serializer(),
        responses=serializers.get_admin_profile_serializer(),
        tags=["dynamic-user-admin"],
    ),
    delete=extend_schema(
        summary="Delete a profile (admin)",
        description="v1.1.0. Deletes the row outright — Django Admin can already do this.",
        responses={204: None},
        tags=["dynamic-user-admin"],
    ),
)
class AdminProfileDetailView(generics.RetrieveUpdateDestroyAPIView[Any]):
    """v1.1.0. ``GET``/``PATCH``/``DELETE`` ``/profiles/{profile_id}/``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    http_method_names = ["get", "patch", "delete", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_profile_detail"
    lookup_url_kwarg = "profile_id"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_admin_profile_serializer()

    def get_queryset(self) -> Any:
        model = resolution.get_profile_model()
        return cast(Any, model)._default_manager.select_related("user")

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = ProfileService.update(instance.user, serializer.validated_data)
        log_admin_action(actor=cast(Any, request.user), obj=updated, action_flag=CHANGE)
        read_serializer = serializers.get_admin_profile_serializer()(updated)
        return Response(read_serializer.data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        log_admin_action(actor=cast(Any, request.user), obj=instance, action_flag=DELETION)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        summary="List settings (admin)",
        description="v1.1.0. Same shape as GET /profiles/ (admin collection), for Setting.",
        responses=serializers.get_admin_setting_serializer(),
        tags=["dynamic-user-admin"],
    ),
    post=extend_schema(
        summary="Create a setting (admin)",
        description="v1.1.0. Any Setting field, including user (writable here only).",
        request=serializers.get_admin_setting_create_serializer(),
        responses={201: serializers.get_admin_setting_serializer()},
        tags=["dynamic-user-admin"],
    ),
)
class AdminSettingListView(generics.ListCreateAPIView[Any]):
    """v1.1.0. ``GET``/``POST`` ``/settings/`` — mirrors :class:`AdminProfileListView` for
    Setting/``SettingAdmin``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_settings_list"
    pagination_class = DefaultPagination

    def get_serializer_class(self) -> type[Any]:
        if self.request.method == "POST":
            return serializers.get_admin_setting_create_serializer()
        return serializers.get_admin_setting_serializer()

    def get_throttles(self) -> list[Any]:
        if self.request.method == "POST":
            self.throttle_scope = "dynamic_user_admin_setting_create"
        return super().get_throttles()

    def get_queryset(self) -> Any:
        model = resolution.get_setting_model()
        validate_query_params(AdminSettingFilterSerializer, self.request.query_params)
        filter_kwargs = safe_filter_kwargs(
            self.request.query_params, allowed_fields=_filterable_model_fields(model)
        )
        return (
            cast(Any, model)
            ._default_manager.filter(**filter_kwargs)
            .select_related("user")
            .order_by("pk")
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        setting = serializer.save()
        log_admin_action(actor=cast(Any, request.user), obj=setting, action_flag=ADDITION)
        read_serializer = serializers.get_admin_setting_serializer()(setting)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a setting (admin)",
        description="v1.1.0. Keyed by the Setting row's own pk, not the owning user's id.",
        responses=serializers.get_admin_setting_serializer(),
        tags=["dynamic-user-admin"],
    ),
    patch=extend_schema(
        summary="Update a setting (admin)",
        description="v1.1.0. Any Setting field, applied via SettingService.update.",
        request=serializers.get_admin_setting_serializer(),
        responses=serializers.get_admin_setting_serializer(),
        tags=["dynamic-user-admin"],
    ),
    delete=extend_schema(
        summary="Delete a setting (admin)",
        description="v1.1.0. Deletes the row outright — Django Admin can already do this.",
        responses={204: None},
        tags=["dynamic-user-admin"],
    ),
)
class AdminSettingDetailView(generics.RetrieveUpdateDestroyAPIView[Any]):
    """v1.1.0. ``GET``/``PATCH``/``DELETE`` ``/settings/{setting_id}/``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    http_method_names = ["get", "patch", "delete", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_setting_detail"
    lookup_url_kwarg = "setting_id"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_admin_setting_serializer()

    def get_queryset(self) -> Any:
        model = resolution.get_setting_model()
        return cast(Any, model)._default_manager.select_related("user")

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = SettingService.update(instance.user, serializer.validated_data)
        log_admin_action(actor=cast(Any, request.user), obj=updated, action_flag=CHANGE)
        read_serializer = serializers.get_admin_setting_serializer()(updated)
        return Response(read_serializer.data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        log_admin_action(actor=cast(Any, request.user), obj=instance, action_flag=DELETION)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------------------------ change log


@extend_schema_view(
    get=extend_schema(
        summary="List change-log entries (admin)",
        description=(
            "v1.1.0. Paginated, filterable list of ChangeLogEntry rows — HistoryMixin's own "
            "audit trail, previously readable only through Django Admin's ChangeLogEntryAdmin."
        ),
        responses=AdminChangeLogEntrySerializer,
        tags=["dynamic-user-admin"],
    )
)
class AdminChangeLogListView(generics.ListAPIView[Any]):
    """v1.1.0. ``GET /change-log/``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_change_log_list"
    pagination_class = DefaultPagination
    serializer_class = AdminChangeLogEntrySerializer

    def get_queryset(self) -> Any:
        validate_query_params(AdminChangeLogFilterSerializer, self.request.query_params)
        filter_kwargs = safe_filter_kwargs(
            self.request.query_params,
            allowed_fields=frozenset({"content_type", "object_id", "actor", "field_name"}),
        )
        return (
            ChangeLogEntry.objects.select_related("content_type", "actor")
            .filter(**filter_kwargs)
            .order_by("-changed_at")
        )


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a change-log entry (admin)",
        responses=AdminChangeLogEntrySerializer,
        tags=["dynamic-user-admin"],
    ),
    delete=extend_schema(
        summary="Delete a change-log entry (admin, superuser-only)",
        description=(
            "v1.1.0. Superuser-only, always — an audit row deleted by anything less is exactly "
            "the tampering an audit trail exists to make visible. Matches the tightened "
            "ChangeLogEntryAdmin gate (docs/CONTRACT.md §10)."
        ),
        responses={204: None},
        tags=["dynamic-user-admin"],
    ),
)
class AdminChangeLogDetailView(generics.RetrieveDestroyAPIView[Any]):
    """v1.1.0. ``GET``/``DELETE`` ``/change-log/{id}/``. No ``PATCH`` — a change-log row is
    write-once, by design (``mixins.HistoryMixin.log_change``), on both interfaces."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    http_method_names = ["get", "delete", "head", "options"]  # noqa: RUF012
    serializer_class = AdminChangeLogEntrySerializer
    queryset = ChangeLogEntry.objects.select_related("content_type", "actor")
    lookup_url_kwarg = "id"

    def get_permissions(self) -> list[Any]:
        permissions = [permission_class() for permission_class in self.permission_classes]
        if self.request.method == "DELETE":
            permissions.append(IsSuperUser())
        return permissions

    def get_throttles(self) -> list[Any]:
        self.throttle_scope = "dynamic_user_admin_change_log_detail"
        return super().get_throttles()

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------------------- groups / perms


@extend_schema_view(
    get=extend_schema(
        summary="List groups (admin, read-only)",
        description=(
            "v1.1.0. Read-only — populates the picker behind PATCH /{id}/'s groups field. Full "
            "Group CRUD stays django.contrib.auth's own admin surface."
        ),
        responses=AdminGroupSerializer,
        tags=["dynamic-user-admin"],
    )
)
class AdminGroupListView(generics.ListAPIView[Any]):
    """v1.1.0. ``GET /groups/``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_groups_list"
    pagination_class = DefaultPagination
    serializer_class = AdminGroupSerializer
    queryset = Group.objects.order_by("name")


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a group (admin, read-only)",
        responses=AdminGroupSerializer,
        tags=["dynamic-user-admin"],
    )
)
class AdminGroupDetailView(generics.RetrieveAPIView[Any]):
    """v1.1.0. ``GET /groups/{id}/``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_group_detail"
    serializer_class = AdminGroupSerializer
    queryset = Group.objects.all()
    lookup_url_kwarg = "id"


@extend_schema_view(
    get=extend_schema(
        summary="List permissions (admin, read-only)",
        description=(
            "v1.1.0. Read-only — populates the picker behind PATCH /{id}/'s user_permissions field."
        ),
        responses=AdminPermissionSerializer,
        tags=["dynamic-user-admin"],
    )
)
class AdminPermissionListView(generics.ListAPIView[Any]):
    """v1.1.0. ``GET /permissions/``."""

    permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
    throttle_scope = "dynamic_user_admin_permissions_list"
    pagination_class = DefaultPagination
    serializer_class = AdminPermissionSerializer
    queryset = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "codename"
    )


# --------------------------------------------------------------------------------- log entries


if django_apps.is_installed("django.contrib.admin"):

    @extend_schema_view(
        get=extend_schema(
            summary="List Django admin-action log entries (admin, read-only)",
            description=(
                "v1.1.0. Django's own django.contrib.admin.models.LogEntry — every write made "
                "through Django Admin is auto-logged here already; this is the read side for a "
                "custom dashboard. Only registered when django.contrib.admin is installed."
            ),
            tags=["dynamic-user-admin"],
        )
    )
    class AdminLogEntryListView(generics.ListAPIView[Any]):
        """v1.1.0. ``GET /log-entries/``."""

        permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
        throttle_scope = "dynamic_user_admin_log_entries_list"
        pagination_class = DefaultPagination

        def get_serializer_class(self) -> type[Any]:
            return serializers.get_admin_log_entry_serializer()

        def get_queryset(self) -> Any:
            from django.contrib.admin.models import LogEntry

            validate_query_params(
                serializers.AdminLogEntryFilterSerializer, self.request.query_params
            )
            filter_kwargs = safe_filter_kwargs(
                self.request.query_params,
                allowed_fields=frozenset({"action_flag", "user", "content_type"}),
            )
            return (
                LogEntry.objects.select_related("user", "content_type")
                .filter(**filter_kwargs)
                .order_by("-action_time")
            )

    @extend_schema_view(
        get=extend_schema(
            summary="Retrieve a Django admin-action log entry (admin, read-only)",
            tags=["dynamic-user-admin"],
        )
    )
    class AdminLogEntryDetailView(generics.RetrieveDestroyAPIView[Any]):
        """v1.1.0. ``GET``/``DELETE`` ``/log-entries/{id}/``. ``DELETE`` is superuser-only,
        always, matching the equally-tightened ``LogEntryAdmin.has_delete_permission`` —
        deleting an audit row is exactly the tampering an audit trail exists to make visible."""

        permission_classes = [IsAuthenticated, IsDynamicUserAdmin]  # noqa: RUF012
        http_method_names = ["get", "delete", "head", "options"]  # noqa: RUF012
        lookup_url_kwarg = "id"

        def get_serializer_class(self) -> type[Any]:
            return serializers.get_admin_log_entry_serializer()

        def get_queryset(self) -> Any:
            from django.contrib.admin.models import LogEntry

            return LogEntry.objects.select_related("user", "content_type")

        def get_permissions(self) -> list[Any]:
            permissions = [permission_class() for permission_class in self.permission_classes]
            if self.request.method == "DELETE":
                permissions.append(IsSuperUser())
            return permissions

        def get_throttles(self) -> list[Any]:
            self.throttle_scope = "dynamic_user_admin_log_entry_detail"
            return super().get_throttles()
