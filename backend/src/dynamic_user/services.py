"""This app's public callable interface — the ONLY place a Profile/Setting update or an
account-deletion state transition happens.

**Phase 2 scope note.** ``docs/CONTRACT.md`` §4 specifies this module in full — ``ProfileService``,
``SettingService``, and all four ``DeletionService`` transitions (``request``/``review``/
``finalize``/``cancel``). Phase 2 implements only ``DeletionService.review`` (plus the two
exception types it needs), pulled forward from Phase 3 so ``admin.py``'s approve/reject action has
something real to call instead of dead code. ``ProfileService.update``, ``SettingService.update``,
and ``DeletionService.request``/``.finalize``/``.cancel`` remain Phase 3 work — their signatures
below are exactly as the contract specifies, bodies not yet implemented.

Every model reference in this module is resolved through ``resolution.py`` or
``settings.AUTH_USER_MODEL`` at call time, never a concrete import — the same rule this repo's
``CLAUDE.md`` states for every other module. Users are typed as
``django.contrib.auth.base_user.AbstractBaseUser`` (Django core, not a concrete ``User`` import);
Profile/Setting return types are ``AbstractProfile``/``AbstractSetting`` — accurate for any
resolved model and import-safe, since importing the *abstract base* from ``dynamic_user.models``
is not importing a concrete swappable model (``docs/CONTRACT.md`` §10 item 5).
"""

from __future__ import annotations

from typing import Any, cast

from django.contrib.auth.base_user import AbstractBaseUser
from django.utils import timezone

from dynamic_user import signals
from dynamic_user.models import AbstractProfile, AbstractSetting, AccountDeletionRequest


class DeletionRequestAlreadyExists(Exception):
    """Raised by ``DeletionService.request()`` when the user already has a pending or approved
    request. Views map this to HTTP 409 (``docs/CONTRACT.md`` §5)."""


class InvalidDeletionState(Exception):
    """Raised by ``DeletionService.review()``/``.finalize()``/``.cancel()`` when called against a
    request not in the required status. Views map this to HTTP 409 (``docs/CONTRACT.md`` §5)."""


class ProfileService:
    @staticmethod
    def update(user: AbstractBaseUser, validated_data: dict[str, Any]) -> AbstractProfile:
        """Writes ``validated_data`` onto ``user``'s Profile (``get_profile_model()``), sends
        ``profile_updated`` with ``changed_fields`` if anything actually changed. No-op fields
        (equal to the current value) are excluded from ``changed_fields``.

        Phase 3 work — not yet implemented.
        """
        raise NotImplementedError("ProfileService.update is implemented in Phase 3.")


class SettingService:
    @staticmethod
    def update(user: AbstractBaseUser, validated_data: dict[str, Any]) -> AbstractSetting:
        """Writes ``validated_data`` onto ``user``'s Setting (``get_setting_model()``). No
        signal — Setting changes are not currently part of the versioned-contract surface.

        Phase 3 work — not yet implemented.
        """
        raise NotImplementedError("SettingService.update is implemented in Phase 3.")


class DeletionService:
    @staticmethod
    def request(user: AbstractBaseUser, *, reason: str = "") -> AccountDeletionRequest:
        """Raises ``DeletionRequestAlreadyExists`` if a pending or approved request already
        exists for this user. Computes ``finalize_at = now() + DELETION_GRACE_PERIOD_DAYS``,
        creates the row with ``status=PENDING``, sends ``deletion_requested``.

        Phase 3 work — not yet implemented.
        """
        raise NotImplementedError("DeletionService.request is implemented in Phase 3.")

    @staticmethod
    def review(
        request_id: int, *, approved: bool, reviewed_by: AbstractBaseUser
    ) -> AccountDeletionRequest:
        """Raises ``InvalidDeletionState`` if the request is not currently ``PENDING``. Moves it
        to ``APPROVED`` or ``REJECTED``, stamps ``reviewed_at``/``reviewed_by``, sends
        ``deletion_reviewed``. Rejecting is terminal — a rejected request cannot later be
        approved; the user must call ``.request()`` again.
        """
        try:
            deletion_request = AccountDeletionRequest.objects.get(pk=request_id)
        except AccountDeletionRequest.DoesNotExist as exc:
            raise InvalidDeletionState(
                f"AccountDeletionRequest {request_id} does not exist."
            ) from exc

        if deletion_request.status != AccountDeletionRequest.Status.PENDING:
            raise InvalidDeletionState(
                f"AccountDeletionRequest {request_id} is '{deletion_request.status}', "
                "not 'pending' — it cannot be reviewed."
            )

        deletion_request.status = (
            AccountDeletionRequest.Status.APPROVED
            if approved
            else AccountDeletionRequest.Status.REJECTED
        )
        deletion_request.reviewed_at = timezone.now()
        # django-stubs binds `reviewed_by`'s Python type to whichever concrete model
        # AUTH_USER_MODEL resolves to under THIS settings module — never the abstract
        # AbstractBaseUser this module's own public signatures intentionally use for
        # import-safety across a swapped host. The two will never exactly agree for a
        # swappable FK; `cast` documents that mismatch instead of silencing it wholesale.
        deletion_request.reviewed_by = cast(Any, reviewed_by)
        deletion_request.save(update_fields=["status", "reviewed_at", "reviewed_by"])

        signals.deletion_reviewed.send(
            sender=AccountDeletionRequest,
            request_id=deletion_request.pk,
            status=deletion_request.status,
            reviewed_by_id=reviewed_by.pk if reviewed_by is not None else None,
        )
        return deletion_request

    @staticmethod
    def finalize(request_id: int) -> None:
        """Raises ``InvalidDeletionState`` if the request is not currently ``APPROVED``.
        Implements ``DYNAMIC_USER["DELETION_MODE"]``. Sends ``deletion_finalized`` with ``mode``
        either way, ``user_id`` captured before any delete.

        Phase 3 work — not yet implemented.
        """
        raise NotImplementedError("DeletionService.finalize is implemented in Phase 3.")

    @staticmethod
    def cancel(user: AbstractBaseUser) -> None:
        """Raises ``InvalidDeletionState`` if the user's current request is not ``PENDING``
        (already approved/rejected/finalized, or no request exists at all).

        Phase 3 work — not yet implemented.
        """
        raise NotImplementedError("DeletionService.cancel is implemented in Phase 3.")
