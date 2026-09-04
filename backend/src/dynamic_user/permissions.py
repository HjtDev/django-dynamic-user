"""User-facing and admin DRF permission classes.

Phase 5 implements ``IsProfileOwner`` and ``IsPublicOrOwner``. Phase 6 adds the admin surface's
three gates:

* ``IsDynamicUserAdmin`` — the one wrapper every admin view imports, never
  ``appkit.permissions.IsAppAdmin`` directly. Resolves
  ``conf.get_setting("ADMIN_REQUIRES_SUPERUSER")`` fresh on every request: ``False`` (default)
  behaves like ``IsAppAdmin`` (``is_staff``); ``True`` tightens to ``is_superuser``. Routing every
  admin view through this one class, rather than repeating the conditional at each view, is what
  makes the setting actually apply everywhere (``docs/CONTRACT.md`` §5).
* ``CanEscalatePrivilege`` — independent of that setting, and never relaxed by it
  (``CLAUDE.md`` rule 5). Runs on every admin ``PATCH`` that can reach
  ``conf.get_privileged_fields()`` (``is_staff``/``is_superuser``/``is_active``/``groups``/
  ``user_permissions``). If the request body touches any of them and the caller isn't an actual
  superuser, the entire request is rejected — never a silent per-field drop.
* ``IsSuperUser`` — the hard floor for ``POST /deletion-requests/{id}/finalize/``, which bypasses
  the grace period entirely and must never be reachable by a staff-only admin, regardless of
  ``ADMIN_REQUIRES_SUPERUSER`` (``docs/CONTRACT.md`` §5).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from appkit.permissions import IsAppAdmin, IsObjectOwner
from rest_framework.exceptions import NotFound
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from dynamic_user import conf

__all__ = [
    "CanEscalatePrivilege",
    "IsDynamicUserAdmin",
    "IsProfileOwner",
    "IsPublicOrOwner",
    "IsSuperUser",
]


class IsProfileOwner(IsObjectOwner):
    """A user may write their own ``Profile``/``Setting``, checked against ``request.user`` —
    never trusted from the URL, since neither self-service route accepts an id at all.

    ``appkit.permissions.IsObjectOwner``'s default ``owner_field = "user"`` already matches both
    models' own O2O field name exactly, and its ``has_object_permission`` already fails closed
    (denies rather than raising) on a misconfigured owner field — no new logic is needed here,
    only the named subclass this app's own permission surface documents.
    """


class IsPublicOrOwner(IsObjectOwner):
    """Gate for ``GET /profiles/{id}/``: allow if ``obj.is_public`` or the requester is the
    owner; a private profile requested by anyone else raises 404, not 403, so a stranger can't
    distinguish "private" from "doesn't exist" (``docs/CONTRACT.md`` §5).

    Raising :exc:`~rest_framework.exceptions.NotFound` here — rather than returning ``False`` and
    letting DRF's own permission-denied path turn it into a 403 — is what makes the existence-leak
    guard fall out of *this class specifically*: swap it for a permission that only checks
    authentication and the private-profile test genuinely fails, per this phase's verification
    requirement. Pre-filtering the queryset instead would satisfy the same test with this class
    removed entirely, which is exactly the false confidence that requirement exists to catch.
    """

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if super().has_object_permission(request, view, obj):
            return True
        if getattr(obj, "is_public", False):
            return True
        raise NotFound


class IsDynamicUserAdmin(BasePermission):
    """The general admin gate every view in ``admin_views.py`` uses, and the only one of the
    three admin permission classes here that ``DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]``
    affects.

    Reads the setting fresh on every call — never once at import/class-definition time — so
    ``override_settings(DYNAMIC_USER=...)`` takes effect on the very next request, in tests and
    at runtime, mirroring ``serializers.py``'s own accessors and this module's own
    ``docs/CONTRACT.md``-documented reasoning for reading settings at call time.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if conf.get_setting("ADMIN_REQUIRES_SUPERUSER"):
            return bool(
                request.user and request.user.is_authenticated and request.user.is_superuser
            )
        return IsAppAdmin().has_permission(request, view)


class CanEscalatePrivilege(BasePermission):
    """Gates any admin write that can reach ``conf.get_privileged_fields()`` — independent of
    ``IsDynamicUserAdmin``/``ADMIN_REQUIRES_SUPERUSER``, and never relaxed by it. Runs from
    ``has_permission`` (DRF's ``initial()`` calls every permission's ``has_permission`` before
    the view handler runs), which is what makes this check happen *before* the view ever touches
    a field — not a per-field filter applied after the fact.

    Safe methods (``GET``/``HEAD``/``OPTIONS``) always pass — this class only ever gates a write.
    A non-``Mapping`` body (a list or scalar JSON payload) is treated as touching no privileged
    field here; DRF's own serializer validation is what rejects a malformed body shape, not this
    permission check.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in SAFE_METHODS:
            return True

        body = request.data if isinstance(request.data, Mapping) else {}
        touched = conf.get_privileged_fields() & set(body)
        if not touched:
            return True

        if request.user and request.user.is_authenticated and request.user.is_superuser:
            return True

        self.message = (
            f"Only a superuser may set the following field(s): {', '.join(sorted(touched))}."
        )
        return False


class IsSuperUser(BasePermission):
    """The hard floor for an irreversible admin action — never loosened by
    ``ADMIN_REQUIRES_SUPERUSER``, since that setting only ever tightens the general admin gate,
    never substitutes for this one (``docs/CONTRACT.md`` §5)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
