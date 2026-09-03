"""User-facing and admin DRF permission classes.

Phase 5 implements ``IsProfileOwner`` and ``IsPublicOrOwner`` below. ``IsDynamicUserAdmin``
(``is_staff`` by default, tightened to ``is_superuser`` when
``DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]`` is ``True``) and ``CanEscalatePrivilege`` — the one
permission class every write path touching ``conf.get_privileged_fields()`` must pass through,
gated on an actual superuser with zero exceptions regardless of ``ADMIN_REQUIRES_SUPERUSER``
(this repo's ``CLAUDE.md`` rule 5: independent of that switch, and never relaxed by it, only an
actual superuser may write ``is_staff``/``is_superuser``/``is_active`` on anyone) — are Phase 6's
admin surface and are not implemented here.
"""

from __future__ import annotations

from typing import Any

from appkit.permissions import IsObjectOwner
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.views import APIView

__all__ = ["IsProfileOwner", "IsPublicOrOwner"]


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
