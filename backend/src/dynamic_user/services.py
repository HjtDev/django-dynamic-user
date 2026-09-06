"""This app's public callable interface — the ONLY place a Profile/Setting update or an
account-deletion state transition happens.

``docs/CONTRACT.md`` §4 specifies this module in full: ``ProfileService``, ``SettingService``, and
all four ``DeletionService`` transitions (``request``/``review``/``finalize``/``cancel``) are
implemented as of Phase 3.

Every model reference in this module is resolved through ``resolution.py`` or
``settings.AUTH_USER_MODEL`` at call time, never a concrete import — the same rule this repo's
``CLAUDE.md`` states for every other module. Users are typed as
``django.contrib.auth.base_user.AbstractBaseUser`` (Django core, not a concrete ``User`` import);
Profile/Setting return types are ``AbstractProfile``/``AbstractSetting`` — accurate for any
resolved model and import-safe, since importing the *abstract base* from ``dynamic_user.models``
is not importing a concrete swappable model (``docs/CONTRACT.md`` §10 item 5).

``DeletionService.cancel()`` deletes the ``PENDING`` row outright rather than moving it to some
"cancelled" status — ``AccountDeletionRequest.Status`` has no such member, adding one is a schema
change this phase doesn't make, and a deleted row lets the user call ``.request()`` again
immediately with no leftover row to clean up later. No signal is sent for it; ``docs/CONTRACT.md``
§3 defines none.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from django.utils.module_loading import import_string

from dynamic_user import conf, resolution, signals
from dynamic_user.models import AbstractProfile, AbstractSetting, AccountDeletionRequest

logger = logging.getLogger(__name__)


class DeletionRequestAlreadyExists(Exception):
    """Raised by ``DeletionService.request()`` when the user already has a pending or approved
    request. Views map this to HTTP 409 (``docs/CONTRACT.md`` §5)."""


class InvalidDeletionState(Exception):
    """Raised by ``DeletionService.review()``/``.finalize()``/``.cancel()``/``.cancel_by_id()``
    when called against a request not in the required status. Views map this to HTTP 409
    (``docs/CONTRACT.md`` §5)."""


class UserService:
    """v1.1.0. The only place a user create/update/delete/password-set happens outside
    :class:`~dynamic_user.managers.UserManager` itself (``create``) or Django's own admin forms.
    Every method resolves the user model through ``django.contrib.auth.get_user_model()`` — never
    a concrete import — mirroring every other service in this module. None of the
    privilege-escalation guarding lives here: that is a view-layer concern
    (``permissions.CanEscalatePrivilege``/``IsSuperUser``), enforced *before* a view ever calls
    into this service, exactly like the existing admin ``PATCH /{id}/`` route already does through
    its serializer.
    """

    @staticmethod
    def create(*, password: str | None = None, **fields: Any) -> AbstractBaseUser:
        """Creates a user via ``UserManager.create_user`` — the one call site that keeps identity
        validation and username generation happening exactly once, inside
        :meth:`~dynamic_user.models.AbstractDynamicUser.save`. ``fields`` is whatever the caller
        resolved (e.g. an admin create serializer's ``validated_data``) — ``username``/``email``
        are both optional keys within it, per this app's v1.1.0 identity rule."""
        model = get_user_model()
        user = cast(Any, model)._default_manager.create_user(password=password, **fields)
        return cast(AbstractBaseUser, user)

    @staticmethod
    def update(
        user: AbstractBaseUser,
        validated_data: dict[str, Any],
        *,
        actor: AbstractBaseUser | None = None,
    ) -> AbstractBaseUser:
        """Writes ``validated_data`` onto ``user``, sends ``user_updated`` with ``changed_fields``
        if anything actually changed — the same diff-and-signal shape as
        :meth:`ProfileService.update`. ``actor`` is accepted for symmetry with
        :meth:`delete`/:meth:`set_password` but not currently part of ``user_updated``'s payload
        (``docs/CONTRACT.md`` §3) — kept as a keyword-only parameter so a future payload addition
        doesn't need a signature change."""
        changed_fields: list[str] = []
        for field, value in validated_data.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed_fields.append(field)

        if changed_fields:
            user.save(update_fields=changed_fields)
            signals.user_updated.send(
                sender=type(user), user_id=user.pk, changed_fields=changed_fields
            )

        return user

    @staticmethod
    def set_password(
        user: AbstractBaseUser, raw_password: str, *, actor: AbstractBaseUser | None = None
    ) -> None:
        """Validates ``raw_password`` against ``AUTH_PASSWORD_VALIDATORS`` (Django's own setting
        — this app defines no opinionated password policy of its own, matching this repo's scope
        boundary for validators), sets it, and sends ``user_password_set`` — carrying no password
        material, only who and whom, so a host or a separate auth-app package can revoke every
        existing session for this user."""
        validate_password(raw_password, user=cast(Any, user))
        user.set_password(raw_password)
        user.save(update_fields=["password"])
        signals.user_password_set.send(
            sender=type(user), user_id=user.pk, actor_id=actor.pk if actor is not None else None
        )

    @staticmethod
    def delete(user: AbstractBaseUser, *, actor: AbstractBaseUser | None = None) -> None:
        """Deletes ``user`` outright and sends ``user_deleted``, ``user_id`` captured before the
        delete — the same reasoning as ``DeletionService.finalize``'s own ``user_id`` capture:
        after the delete there is no row left to read it from."""
        user_id = user.pk
        user.delete()
        signals.user_deleted.send(
            sender=type(user), user_id=user_id, actor_id=actor.pk if actor is not None else None
        )


class ProfileService:
    @staticmethod
    def update(user: AbstractBaseUser, validated_data: dict[str, Any]) -> AbstractProfile:
        """Writes ``validated_data`` onto ``user``'s Profile (``get_profile_model()``), sends
        ``profile_updated`` with ``changed_fields`` if anything actually changed. No-op fields
        (equal to the current value) are excluded from ``changed_fields``.

        ``get_or_create``s the row rather than assuming one already exists — a host running
        ``AUTO_CREATE_PROFILE=False``, or a user created before this app was installed, must
        still be able to ``PATCH`` their profile instead of getting a 404/500 from a missing row.
        """
        model = resolution.get_profile_model()
        # resolution.py types this as the bare `type[Model]`, which django-stubs gives no
        # `.objects` — the same swappable-model/stub mismatch `DeletionService.review()` below
        # documents for `reviewed_by`. `cast` records that mismatch instead of silencing it
        # wholesale.
        profile, _ = cast(Any, model).objects.get_or_create(user=user)

        changed_fields: list[str] = []
        for field, value in validated_data.items():
            if getattr(profile, field) != value:
                setattr(profile, field, value)
                changed_fields.append(field)

        if changed_fields:
            profile.save(update_fields=changed_fields)
            signals.profile_updated.send(
                sender=model, user_id=user.pk, changed_fields=changed_fields
            )

        return cast(AbstractProfile, profile)


class SettingService:
    @staticmethod
    def update(user: AbstractBaseUser, validated_data: dict[str, Any]) -> AbstractSetting:
        """Writes ``validated_data`` onto ``user``'s Setting (``get_setting_model()``), sends
        ``setting_updated`` with ``changed_fields`` if anything actually changed — v1.1.0 closes
        the asymmetry with :meth:`ProfileService.update` that ``docs/CONTRACT.md`` §11 had left
        as an open item. Additive: no existing receiver relied on Setting changes staying silent.

        Same ``get_or_create`` reasoning as :meth:`ProfileService.update`.
        """
        model = resolution.get_setting_model()
        setting, _ = cast(Any, model).objects.get_or_create(user=user)

        changed_fields: list[str] = []
        for field, value in validated_data.items():
            if getattr(setting, field) != value:
                setattr(setting, field, value)
                changed_fields.append(field)

        if changed_fields:
            setting.save(update_fields=changed_fields)
            signals.setting_updated.send(
                sender=model, user_id=user.pk, changed_fields=changed_fields
            )

        return cast(AbstractSetting, setting)


class DeletionService:
    @staticmethod
    def current(user: AbstractBaseUser) -> AccountDeletionRequest | None:
        """The user's active request — ``status`` ``PENDING`` or ``APPROVED`` — or ``None``.

        Matches ``.request()``'s own "already exists" predicate exactly, so "you may not create
        one" and "here is the one you have" (``GET /me/deletion-request/``,
        ``docs/CONTRACT.md`` §5) can never disagree about what counts as active.
        """
        return AccountDeletionRequest.objects.filter(
            user=cast(Any, user),
            status__in=[
                AccountDeletionRequest.Status.PENDING,
                AccountDeletionRequest.Status.APPROVED,
            ],
        ).first()

    @staticmethod
    def request(user: AbstractBaseUser, *, reason: str = "") -> AccountDeletionRequest:
        """Raises ``DeletionRequestAlreadyExists`` if a pending or approved request already
        exists for this user. Computes ``finalize_at = now() + DELETION_GRACE_PERIOD_DAYS``,
        creates the row with ``status=PENDING``, sends ``deletion_requested``.
        """
        already_active = AccountDeletionRequest.objects.filter(
            user=cast(Any, user),
            status__in=[
                AccountDeletionRequest.Status.PENDING,
                AccountDeletionRequest.Status.APPROVED,
            ],
        ).exists()
        if already_active:
            raise DeletionRequestAlreadyExists(
                f"User {user.pk} already has a pending or approved deletion request."
            )

        grace_period_days = conf.get_setting("DELETION_GRACE_PERIOD_DAYS")
        finalize_at = timezone.now() + timedelta(days=grace_period_days)

        deletion_request = AccountDeletionRequest.objects.create(
            user=cast(Any, user),
            reason=reason,
            status=AccountDeletionRequest.Status.PENDING,
            finalize_at=finalize_at,
        )

        signals.deletion_requested.send(
            sender=AccountDeletionRequest,
            user_id=user.pk,
            request_id=deletion_request.pk,
            finalize_at=deletion_request.finalize_at,
        )
        return deletion_request

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
        """Raises ``InvalidDeletionState`` if the request is not currently ``APPROVED`` — never a
        silent no-op. Implements ``DYNAMIC_USER["DELETION_MODE"]``: ``"hard_delete"`` deletes the
        user row (Profile/Setting/this request cascade per each model's own ``on_delete``);
        ``"anonymize"`` calls the conf-resolved ``DELETION_ANONYMIZE_FUNCTION`` instead and moves
        this request to ``FINALIZED`` (nothing to cascade-delete in this mode). Sends
        ``deletion_finalized`` with ``mode`` either way, ``user_id`` captured before any delete —
        after a ``hard_delete`` there is no row left to read it from.

        Fails closed on a misconfigured anonymize mode: raises ``ImproperlyConfigured`` rather
        than silently falling back to ``hard_delete`` if ``DELETION_ANONYMIZE_FUNCTION`` is unset,
        or if ``DELETION_MODE`` itself is neither ``"hard_delete"`` nor ``"anonymize"``. This is
        the same invariant ``dynamic_user.E003`` (``checks.py``) catches at ``manage.py check``
        time — this raise is the request-time backstop for a management command or task that
        skipped system checks.
        """
        try:
            deletion_request = AccountDeletionRequest.objects.get(pk=request_id)
        except AccountDeletionRequest.DoesNotExist as exc:
            raise InvalidDeletionState(
                f"AccountDeletionRequest {request_id} does not exist."
            ) from exc

        if deletion_request.status != AccountDeletionRequest.Status.APPROVED:
            raise InvalidDeletionState(
                f"AccountDeletionRequest {request_id} is '{deletion_request.status}', "
                "not 'approved' — it cannot be finalized."
            )

        mode = conf.get_setting("DELETION_MODE")
        user_id = deletion_request.user_id

        if mode == "hard_delete":
            deletion_request.user.delete()
        elif mode == "anonymize":
            dotted_path = conf.get_setting("DELETION_ANONYMIZE_FUNCTION")
            if not dotted_path:
                raise ImproperlyConfigured(
                    'DYNAMIC_USER["DELETION_MODE"] is "anonymize" but '
                    'DYNAMIC_USER["DELETION_ANONYMIZE_FUNCTION"] is not set.'
                )
            try:
                anonymize = import_string(dotted_path)
            except ImportError as exc:
                raise ImproperlyConfigured(
                    f'DYNAMIC_USER["DELETION_ANONYMIZE_FUNCTION"] names "{dotted_path}", '
                    "which could not be imported."
                ) from exc
            if not callable(anonymize):
                raise ImproperlyConfigured(
                    f'DYNAMIC_USER["DELETION_ANONYMIZE_FUNCTION"] names "{dotted_path}", '
                    "which is not callable."
                )
            anonymize(deletion_request.user)
            deletion_request.status = AccountDeletionRequest.Status.FINALIZED
            deletion_request.save(update_fields=["status"])
        else:
            raise ImproperlyConfigured(
                f'DYNAMIC_USER["DELETION_MODE"] is "{mode}", which is neither "hard_delete" '
                'nor "anonymize".'
            )

        signals.deletion_finalized.send(sender=AccountDeletionRequest, user_id=user_id, mode=mode)

    @staticmethod
    def cancel(user: AbstractBaseUser) -> None:
        """Raises ``InvalidDeletionState`` if the user's current request is not ``PENDING``
        (already approved/rejected/finalized, or no request exists at all). Deletes the row on
        success — see this module's docstring for why cancellation has no dedicated status."""
        deletion_request = AccountDeletionRequest.objects.filter(
            user=cast(Any, user), status=AccountDeletionRequest.Status.PENDING
        ).first()
        if deletion_request is None:
            raise InvalidDeletionState(f"User {user.pk} has no pending deletion request to cancel.")
        deletion_request.delete()

    @staticmethod
    def cancel_by_id(request_id: int) -> None:
        """v1.1.0. Admin-side cancel — same no-dedicated-status reasoning as :meth:`cancel`, but
        reached by request id rather than only the current user's own row, since an admin cancels
        on someone else's behalf. Accepts a request currently ``PENDING`` *or* ``APPROVED`` —
        unlike :meth:`cancel`, which only ever sees the caller's own current (therefore
        ``PENDING``-only, per :meth:`current`) request — because an admin reasonably wants to
        withdraw a request they already approved but haven't finalized yet. Raises
        ``InvalidDeletionState`` if the request doesn't exist or is already ``REJECTED``/
        ``FINALIZED``."""
        try:
            deletion_request = AccountDeletionRequest.objects.get(pk=request_id)
        except AccountDeletionRequest.DoesNotExist as exc:
            raise InvalidDeletionState(
                f"AccountDeletionRequest {request_id} does not exist."
            ) from exc

        cancellable = (
            AccountDeletionRequest.Status.PENDING,
            AccountDeletionRequest.Status.APPROVED,
        )
        if deletion_request.status not in cancellable:
            raise InvalidDeletionState(
                f"AccountDeletionRequest {request_id} is '{deletion_request.status}', "
                "not 'pending' or 'approved' — it cannot be cancelled."
            )
        deletion_request.delete()
