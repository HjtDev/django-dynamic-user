"""Self-service, user-facing DRF views.

``docs/CONTRACT.md`` §5's self-service half — see own info, edit own profile/setting, browse
others' public profiles, request/cancel account deletion — gated by ``IsProfileOwner``/
``IsPublicOrOwner`` from ``permissions.py``, built entirely through
``serializers.build_serializer()``'s accessors from Phase 4. No endpoint here ever edits anyone
else's data — there is no such route on this surface (this repo's scope-boundary table); the one
place an id is ever accepted is ``PublicProfileDetailView``, and it is read-only.

Every ``get_serializer_class()`` below calls a Phase 4 accessor function directly rather than
binding a ``serializer_class`` attribute at import time — the accessors re-read
``conf.get_setting(...)`` on every call specifically so ``override_settings(DYNAMIC_USER=...)``
takes effect on the very next request, in tests and at runtime, with no process restart
(``serializers.py``'s own docstring). Binding at import time would freeze the field list and
silently break both the swapped settings leg and every ``override_settings`` test.
"""

from __future__ import annotations

from typing import Any, cast

from appkit.mixins import CachedListMixin
from appkit.pagination import DefaultPagination
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from dynamic_user import resolution, serializers
from dynamic_user.permissions import IsProfileOwner, IsPublicOrOwner
from dynamic_user.serializers import DeletionRequestCreateSerializer, DeletionRequestSerializer
from dynamic_user.services import (
    DeletionRequestAlreadyExists,
    DeletionService,
    InvalidDeletionState,
    ProfileService,
    SettingService,
)

__all__ = [
    "DeletionRequestConflict",
    "MeView",
    "MyDeletionRequestView",
    "MyProfileView",
    "MySettingView",
    "PublicProfileDetailView",
    "PublicProfileListView",
]


class DeletionRequestConflict(APIException):
    """Maps both ``DeletionService`` state-conflict exceptions to the contract's ``409`` — DRF
    ships no built-in 409 exception. Resolves to appkit's generic ``"error"`` envelope code
    (``appkit.exceptions._code_for``'s documented catch-all for an ``APIException`` it doesn't
    specifically recognize), which keeps the response inside the fixed ten-code envelope without
    inventing an eleventh."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The deletion request is in a conflicting state."
    default_code = "error"


@extend_schema_view(
    # Keyed by HTTP method, not a ViewSet's `.action` — a plain GenericAPIView has none, so
    # AutoSchema falls back to `self.method.lower()` (verified against cleanup_app's own
    # admin_views.py, which hit this exact resolution rule first).
    get=extend_schema(
        summary="Get my account info",
        description=(
            "USER_READ_FIELDS, entirely read-only — includes locked fields for visibility, "
            "none of them writable from here or anywhere else on this surface."
        ),
        responses=serializers.get_user_read_serializer(),
        tags=["dynamic-user"],
    )
)
class MeView(generics.RetrieveAPIView[Any]):
    """``GET /me/``. No PATCH exists here at all — ``USER_EDITABLE_FIELDS`` has no wired route on
    this surface yet (``docs/CONTRACT.md`` §5); PUT/PATCH/DELETE all 405 since ``RetrieveAPIView``
    defines no handler for them."""

    permission_classes = [IsAuthenticated]  # noqa: RUF012 -- APIView types this as an instance var
    throttle_scope = "dynamic_user_me"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_user_read_serializer()

    def get_object(self) -> Any:
        return cast(Any, self.request.user)


@extend_schema_view(
    get=extend_schema(
        summary="Get my profile",
        description="PROFILE_EDITABLE_FIELDS + PROFILE_READ_FIELDS (union).",
        responses=serializers.get_profile_read_serializer(),
        tags=["dynamic-user"],
    ),
    patch=extend_schema(
        summary="Update my profile",
        description="PROFILE_EDITABLE_FIELDS, applied via ProfileService.update.",
        request=serializers.get_profile_edit_serializer(),
        responses=serializers.get_profile_read_serializer(),
        tags=["dynamic-user"],
    ),
)
class MyProfileView(generics.RetrieveUpdateAPIView[Any]):
    """``GET``/``PATCH`` ``/me/profile/``. The object is always resolved from ``request.user`` —
    never a URL-supplied id, there is no such kwarg on this route at all — and
    ``check_object_permissions`` is called explicitly from the overridden :meth:`get_object` so
    ``IsProfileOwner`` genuinely runs rather than being decorative (it will always pass here,
    since the object is always the caller's own, but the guide requires the check actually
    execute, not just be listed).

    ``PUT`` is deliberately unavailable — ``docs/CONTRACT.md`` §5 lists no full-replace route, and
    ``RetrieveUpdateAPIView`` would otherwise expose one via ``UpdateModelMixin``.
    """

    permission_classes = [IsAuthenticated, IsProfileOwner]  # noqa: RUF012
    http_method_names = ["get", "patch", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_me"

    def get_serializer_class(self) -> type[Any]:
        if self.request.method == "PATCH":
            return serializers.get_profile_edit_serializer()
        return serializers.get_profile_read_serializer()

    def get_throttles(self) -> list[Any]:
        if self.request.method == "PATCH":
            self.throttle_scope = "dynamic_user_profile_update"
        return super().get_throttles()

    def get_object(self) -> Any:
        model = resolution.get_profile_model()
        profile, _ = cast(Any, model).objects.get_or_create(user=self.request.user)
        self.check_object_permissions(self.request, profile)
        return profile

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = ProfileService.update(cast(Any, request.user), serializer.validated_data)
        read_serializer = serializers.get_profile_read_serializer()(updated)
        return Response(read_serializer.data)


@extend_schema_view(
    get=extend_schema(
        summary="Get my setting",
        description="SETTING_EDITABLE_FIELDS + SETTING_READ_FIELDS (union).",
        responses=serializers.get_setting_read_serializer(),
        tags=["dynamic-user"],
    ),
    patch=extend_schema(
        summary="Update my setting",
        description="SETTING_EDITABLE_FIELDS, applied via SettingService.update.",
        request=serializers.get_setting_edit_serializer(),
        responses=serializers.get_setting_read_serializer(),
        tags=["dynamic-user"],
    ),
)
class MySettingView(generics.RetrieveUpdateAPIView[Any]):
    """``GET``/``PATCH`` ``/me/setting/`` — same shape as :class:`MyProfileView`, over
    ``SettingService`` instead of ``ProfileService``."""

    permission_classes = [IsAuthenticated, IsProfileOwner]  # noqa: RUF012
    http_method_names = ["get", "patch", "head", "options"]  # noqa: RUF012
    throttle_scope = "dynamic_user_me"

    def get_serializer_class(self) -> type[Any]:
        if self.request.method == "PATCH":
            return serializers.get_setting_edit_serializer()
        return serializers.get_setting_read_serializer()

    def get_throttles(self) -> list[Any]:
        if self.request.method == "PATCH":
            self.throttle_scope = "dynamic_user_setting_update"
        return super().get_throttles()

    def get_object(self) -> Any:
        model = resolution.get_setting_model()
        setting, _ = cast(Any, model).objects.get_or_create(user=self.request.user)
        self.check_object_permissions(self.request, setting)
        return setting

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = SettingService.update(cast(Any, request.user), serializer.validated_data)
        read_serializer = serializers.get_setting_read_serializer()(updated)
        return Response(read_serializer.data)


@extend_schema_view(
    get=extend_schema(
        summary="List public profiles",
        description=(
            "Paginated, cached list of every profile with is_public=True. "
            "PROFILE_PUBLIC_FIELDS plus a nested user block from USER_PUBLIC_FIELDS."
        ),
        responses=serializers.get_public_profile_serializer(),
        tags=["dynamic-user"],
    )
)
class PublicProfileListView(CachedListMixin, generics.ListAPIView[Any]):
    """``GET /profiles/``. ``CachedListMixin`` must precede ``ListAPIView`` in the MRO — it only
    overrides ``list()`` (appkit's own requirement, ``mixins.py``'s docstring)."""

    permission_classes = [IsAuthenticated]  # noqa: RUF012
    throttle_scope = "dynamic_user_profiles_list"
    pagination_class = DefaultPagination
    cache_namespace = "dynamic_user"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_public_profile_serializer()

    def get_queryset(self) -> Any:
        model = resolution.get_profile_model()
        # Explicit ordering: pagination over an unordered queryset triggers Django's own
        # UnorderedObjectListWarning and can silently reorder between pages.
        return (
            cast(Any, model)
            ._default_manager.filter(is_public=True)
            .select_related("user")
            .order_by("pk")
        )


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a public profile",
        description=(
            "PROFILE_PUBLIC_FIELDS plus a nested user block from USER_PUBLIC_FIELDS, for one "
            "profile. {id} is the target user's id, not the Profile row's own pk. 404 (not "
            "403) when the profile is private and the requester isn't the owner."
        ),
        responses=serializers.get_public_profile_serializer(),
        tags=["dynamic-user"],
    )
)
class PublicProfileDetailView(generics.RetrieveAPIView[Any]):
    """``GET /profiles/{id}/`` — the one route on this surface that accepts a URL-supplied id,
    because its entire purpose is looking up *someone else's* public data
    (``docs/CONTRACT.md`` §5). Read-only. ``lookup_field`` is ``user_id``, not the default
    ``pk`` — the id in the URL names the target user, not the Profile row (§10 item 6)."""

    permission_classes = [IsAuthenticated, IsPublicOrOwner]  # noqa: RUF012
    throttle_scope = "dynamic_user_profile_retrieve"
    lookup_field = "user_id"
    lookup_url_kwarg = "id"

    def get_serializer_class(self) -> type[Any]:
        return serializers.get_public_profile_serializer()

    def get_queryset(self) -> Any:
        model = resolution.get_profile_model()
        return cast(Any, model)._default_manager.select_related("user")


class MyDeletionRequestView(APIView):
    """``POST``/``GET``/``DELETE`` ``/me/deletion-request/`` — calls ``DeletionService`` directly
    for every state transition, never touching the model layer itself (the guide's own
    requirement)."""

    permission_classes = [IsAuthenticated]  # noqa: RUF012
    throttle_scope = "dynamic_user_deletion_request"

    @extend_schema(
        summary="Request account deletion",
        description=(
            "Starts the grace-period countdown. 409 (not 500) if a request is already "
            "pending or approved, rather than creating a duplicate."
        ),
        request=DeletionRequestCreateSerializer,
        responses={201: DeletionRequestSerializer},
        tags=["dynamic-user"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = DeletionRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            deletion_request = DeletionService.request(
                cast(Any, request.user), reason=serializer.validated_data.get("reason", "")
            )
        except DeletionRequestAlreadyExists as exc:
            raise DeletionRequestConflict(str(exc)) from exc
        return Response(
            DeletionRequestSerializer(deletion_request).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Get my current deletion request",
        description="The caller's active (pending or approved) request, or 404 if none exists.",
        responses={200: DeletionRequestSerializer},
        tags=["dynamic-user"],
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        deletion_request = DeletionService.current(cast(Any, request.user))
        if deletion_request is None:
            raise NotFound("No active deletion request.")
        return Response(DeletionRequestSerializer(deletion_request).data)

    @extend_schema(
        summary="Cancel my deletion request",
        description="409 (not 500) if the caller's request isn't currently pending.",
        responses={204: None},
        tags=["dynamic-user"],
    )
    def delete(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            DeletionService.cancel(cast(Any, request.user))
        except InvalidDeletionState as exc:
            raise DeletionRequestConflict(str(exc)) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)
