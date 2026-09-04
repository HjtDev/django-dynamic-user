"""The settings-driven serializer factory — so a host's subclassed model needs zero view-layer
changes.

Phase 4 implements ``build_serializer()``, resolving field allowlists from ``conf.py`` against
the *resolved* model (``resolution.py``, never a hardcoded default) at call time — never baked
into a model's class attributes or ``Meta`` (this repo's ``CLAUDE.md`` rule 2: a settings change
must never produce a migration diff). Raises ``django.core.exceptions.ImproperlyConfigured`` if
called before ``checks.py``'s ``dynamic_user.E005`` allowlist check has had a chance to run
(``docs/CONTRACT.md`` §6), naming the offending field and setting key.

``password`` is excluded from every serializer this factory can produce or accept,
unconditionally — a hard deny-list, never a per-call opt-out (``docs/CONTRACT.md`` §5, this
repo's ``CLAUDE.md`` rule 3: no serializer, on either surface, ever emits ``password`` or a
hash).

**Caching, and why it's split in two layers.** ``build_serializer()`` itself is
``functools.lru_cache``d, keyed on a hashable form of ``(model, fields, read_only_fields,
extra_kwargs)`` — the same ``(model, fields)`` combination always returns the *same* class object
(``is``, not ``==``), which is what lets ``drf-spectacular`` name the generated OpenAPI component
stably across requests instead of emitting a fresh, colliding component per call. The module-level
accessors below (``get_user_read_serializer()`` etc.) are deliberately **not** cached themselves —
each one re-reads ``conf.get_setting(...)`` on every call (mirroring ``validators.run_validators``'s
own "the setting itself is read fresh, only the expensive derived result is cached" split) so
``override_settings(DYNAMIC_USER=...)`` takes effect on the very next call, in tests and at
runtime, with no process restart. Caching still holds at the ``build_serializer()`` layer
underneath, so repeated accessor calls with an unchanged setting still return the identical class.

**The two-cooperating-mechanisms guard (``docs/CONTRACT.md`` §6).** A name in a ``*_FIELDS``
allowlist that doesn't exist on the resolved model is caught by two independent paths that share
one message ( :func:`_unknown_field_message` ), so the same misconfiguration reads identically
however it's discovered:

1. ``checks.py``'s ``dynamic_user.E005`` system check, at ``manage.py check``/startup time,
   validating every configured allowlist directly against the resolved model and naming the
   setting key.
2. Every accessor in this module validates its own fields against the resolved model, with its
   own setting key attached, *before* calling :func:`build_serializer` — so a management command
   that skips system checks still gets the same named error the first time it actually reaches a
   wired serializer, never a silent drop and never a 500 mid-request. :func:`build_serializer`
   itself also validates on every call, generically (no setting key — it doesn't know one), as the
   final backstop for direct callers who bypass the accessors entirely.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from functools import cache
from typing import Any, ClassVar, Final, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.dispatch import receiver
from django.test.signals import setting_changed
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from dynamic_user import conf, resolution
from dynamic_user.models import AccountDeletionRequest

#: Never included in any serializer this factory builds, unconditionally — no per-call opt-out,
#: no alias/`source=` trick around it (see :func:`_build_serializer`'s deny-list check below).
DENIED_FIELDS: Final[frozenset[str]] = frozenset({"password"})

#: The settings this module's cache must never survive a change to — mirrors resolution.py's own
#: warning about a hand-rolled cache going stale across the app registry's lifecycle. Deliberately
#: excludes "DYNAMIC_USER": that key's values are already part of every cache key (each accessor
#: reads it fresh and passes the result into build_serializer()), so clearing here would do
#: nothing but discard otherwise-valid cache entries.
_CACHE_SENSITIVE_SETTINGS: Final[frozenset[str]] = frozenset(
    {
        "AUTH_USER_MODEL",
        "DYNAMIC_USER_PROFILE_MODEL",
        "DYNAMIC_USER_SETTING_MODEL",
        "INSTALLED_APPS",
    }
)

ExtraKwargs = Mapping[str, Mapping[str, Any]]
_FrozenExtraKwargs = tuple[tuple[str, tuple[tuple[str, Any], ...]], ...]


def build_serializer(
    model: type[Model],
    fields: Sequence[str],
    *,
    read_only_fields: Sequence[str] = (),
    extra_kwargs: ExtraKwargs | None = None,
) -> type[serializers.ModelSerializer[Any]]:
    """Build (or return the cached) :class:`~rest_framework.serializers.ModelSerializer` subclass
    for ``model`` restricted to ``fields``.

    Built once per ``(model, fields, read_only_fields, extra_kwargs)`` combination and cached —
    calling this twice with an equal set of arguments returns the *same* class object, never a
    fresh one (see this module's docstring for why that identity matters).

    Args:
        model: the *resolved* model to build a serializer for — always
            ``resolution.get_profile_model()``/``get_setting_model()``/
            ``django.contrib.auth.get_user_model()``, never a hardcoded default.
        fields: field names to include, in order — this becomes the serializer's ``Meta.fields``
            and, in the read output, its key order.
        read_only_fields: subset of ``fields`` to mark read-only.
        extra_kwargs: passed through to ``Meta.extra_kwargs`` verbatim (e.g. ``min_length``,
            ``required``, ``source``), after the deny-list check below.

    Raises:
        ImproperlyConfigured: ``fields``/``read_only_fields`` names ``password`` (or an
            ``extra_kwargs`` entry's ``source`` resolves to it), or names a field that doesn't
            exist on ``model`` — naming the offending field, but with no setting key attached
            (this function has no ``setting_key`` parameter; callers that have one — every
            accessor below — validate with it *before* calling in, so a user reaching this
            through the wired surface sees the setting-key-aware message instead).
    """
    return _build_serializer(
        model,
        tuple(fields),
        tuple(read_only_fields),
        _freeze_extra_kwargs(extra_kwargs),
    )


@cache
def _build_serializer(
    model: type[Model],
    fields: tuple[str, ...],
    read_only_fields: tuple[str, ...],
    extra_kwargs: _FrozenExtraKwargs,
) -> type[serializers.ModelSerializer[Any]]:
    """The cached implementation behind :func:`build_serializer` — not part of this module's
    public surface. Takes only hashable arguments, since ``functools.lru_cache`` requires them."""
    _check_denied(fields, extra_kwargs)
    _validate_known_fields(model, fields)
    _validate_known_fields(model, read_only_fields)

    meta_attrs: dict[str, Any] = {
        "model": model,
        "fields": list(fields),
        "read_only_fields": list(read_only_fields),
    }
    if extra_kwargs:
        meta_attrs["extra_kwargs"] = {name: dict(opts) for name, opts in extra_kwargs}

    meta = type("Meta", (), meta_attrs)
    name = _generated_name(model, fields, read_only_fields, extra_kwargs)
    serializer_cls = type(name, (serializers.ModelSerializer,), {"Meta": meta})
    return cast("type[serializers.ModelSerializer[Any]]", serializer_cls)


def _freeze_extra_kwargs(extra_kwargs: ExtraKwargs | None) -> _FrozenExtraKwargs:
    """Normalize ``extra_kwargs`` into a hashable, order-stable form for the ``lru_cache`` key.

    Sorting is safe even when option values aren't themselves comparable: dict keys within one
    field's options are unique, so tuple comparison during sort never needs to fall through to
    comparing the (possibly uncomparable) values.
    """
    if not extra_kwargs:
        return ()
    return tuple((name, tuple(sorted(opts.items()))) for name, opts in sorted(extra_kwargs.items()))


def _check_denied(fields: tuple[str, ...], extra_kwargs: _FrozenExtraKwargs) -> None:
    """Refuse ``DENIED_FIELDS`` unconditionally — named directly in ``fields``, or reached
    indirectly via an ``extra_kwargs`` ``source=`` alias. Not part of this module's public
    surface."""
    denied_direct = DENIED_FIELDS & set(fields)
    if denied_direct:
        raise ImproperlyConfigured(
            f"build_serializer() refuses to include {sorted(denied_direct)!r} — "
            "this factory never emits password or a hash, unconditionally."
        )

    for field_name, opts in extra_kwargs:
        source = dict(opts).get("source")
        if source in DENIED_FIELDS:
            raise ImproperlyConfigured(
                f"build_serializer() refuses field '{field_name}': its extra_kwargs source "
                f"'{source}' resolves to a denied field. This factory never emits password or a "
                "hash, unconditionally, including via a source= alias."
            )


def _valid_field_names(model: type[Model]) -> frozenset[str]:
    """The set of names :func:`build_serializer` accepts for ``model`` — every forward, concrete
    field plus forward many-to-many fields (e.g. ``PermissionsMixin``'s ``groups``/
    ``user_permissions``), and the ``"pk"`` alias. Deliberately excludes reverse relations
    (``profile``, ``deletion_requests``, ...) — naming one of this model's own reverse accessors
    in a ``DYNAMIC_USER`` allowlist is not a shape this factory supports; those are separate
    models with their own settings-driven surface."""
    names = {
        f.name
        for f in model._meta.get_fields()
        if getattr(f, "concrete", False)
        or (getattr(f, "many_to_many", False) and not getattr(f, "auto_created", False))
    }
    names.add("pk")
    return frozenset(names)


def _validate_known_fields(
    model: type[Model], fields: Iterable[str], setting_key: str | None = None
) -> None:
    """Raise :exc:`ImproperlyConfigured` naming the first field in ``fields`` that doesn't exist
    on ``model``. Not part of this module's public surface — call via :func:`build_serializer`
    (generic) or from an accessor with its own ``setting_key`` (setting-key-aware)."""
    valid = _valid_field_names(model)
    for field in fields:
        if field not in valid:
            raise ImproperlyConfigured(_unknown_field_message(field, model, setting_key))


def _unknown_field_message(field: str, model: type[Model], setting_key: str | None = None) -> str:
    """The one message shape shared by :func:`build_serializer`'s own guard, every accessor
    below, and ``checks.py``'s ``dynamic_user.E005`` — so the same misconfiguration reads
    identically whichever of the two cooperating mechanisms (``docs/CONTRACT.md`` §6) catches it
    first."""
    label = model._meta.label
    if setting_key:
        return f'DYNAMIC_USER["{setting_key}"] names "{field}", which does not exist on {label}.'
    return f'build_serializer() was given field "{field}", which does not exist on {label}.'


def _generated_name(
    model: type[Model],
    fields: tuple[str, ...],
    read_only_fields: tuple[str, ...],
    extra_kwargs: _FrozenExtraKwargs,
) -> str:
    """A deterministic, per-process-stable class name for the generated serializer — builtin
    ``hash()`` is salted per interpreter run and would make ``drf-spectacular``'s emitted OpenAPI
    component name (therefore the generated TypeScript type name, ``APP-DESIGN.md`` §12) churn on
    every process restart even with identical settings."""
    digest = hashlib.sha256(
        repr((model._meta.label, fields, read_only_fields, extra_kwargs)).encode()
    ).hexdigest()[:6]
    return f"{model.__name__}{digest.upper()}Serializer"


@receiver(setting_changed)
def _clear_cache_on_model_swap(sender: object, setting: str, **kwargs: Any) -> None:
    """Drop every cached serializer class when a setting that changes which concrete model a
    cache key even refers to changes underneath it (``override_settings(AUTH_USER_MODEL=...)``,
    an app-registry-affecting ``INSTALLED_APPS`` override, etc.) — a defensive measure against
    holding a strong reference to a model class from a torn-down app registry, mirroring
    ``resolution.py``'s own warning about a hand-rolled cache going stale across exactly this kind
    of event. Deliberately not triggered by a plain ``DYNAMIC_USER`` change — the field list is
    already part of every cache key, so nothing there needs invalidating.
    """
    if setting in _CACHE_SENSITIVE_SETTINGS:
        _build_serializer.cache_clear()
        _component_name_cache.clear()


_component_name_cache: dict[
    tuple[type[serializers.ModelSerializer[Any]], str], type[serializers.ModelSerializer[Any]]
] = {}


def _with_component_name(
    base: type[serializers.ModelSerializer[Any]], component_name: str
) -> type[serializers.ModelSerializer[Any]]:
    """Wraps ``base`` in a thin, cached subclass carrying a pinned ``drf-spectacular`` OpenAPI
    component name, via ``@extend_schema_serializer(component_name=...)``.

    ``build_serializer()`` names its generated classes from a content hash
    (:func:`_generated_name`) — deterministic within one field-set/settings combination, but a
    host editing a ``DYNAMIC_USER`` field allowlist changes the hash, and therefore the emitted
    OpenAPI component name, and therefore the generated TypeScript type name in
    ``frontend/src/schema.d.ts`` — exactly the unstable-component-name failure
    ``docs/APP-DESIGN.md`` §12 warns about. Every module-level accessor below that is wired to a
    ``views.py``/``admin_views.py`` ``extend_schema(...)`` call (i.e. one whose name actually
    reaches ``drf-spectacular``'s introspection) routes its return value through here, so the
    *emitted* component name stays a fixed literal regardless of settings.

    Subclasses ``base`` rather than decorating it in place — ``@extend_schema_serializer``
    mutates the class object it's given (``drf_spectacular.utils.set_override``), and ``base`` is
    a ``build_serializer()``-cached object two different accessors could, under an unusual
    settings override that made their field tuples collide, legitimately share; mutating it
    directly would let whichever accessor calls last silently win the component name for both.
    A fresh, empty subclass sidesteps that and exactly mirrors
    :func:`get_public_profile_serializer`'s own ``WithUser`` subclassing, done for the same
    reason.

    Cached on ``(base, component_name)`` so repeat calls return the *same* wrapped class object —
    preserving this module's ``is``-identity contract (``test_accessor_calls_are_cached_too``).
    Cleared alongside :func:`_build_serializer` by :func:`_clear_cache_on_model_swap`, since a
    cached wrapper here holds the same kind of reference to a torn-down app registry's model class
    that motivates that clear in the first place.
    """
    key = (base, component_name)
    cached = _component_name_cache.get(key)
    if cached is not None:
        return cached
    subclass = type(f"{component_name}Serializer", (base,), {})
    extend_schema_serializer(component_name=component_name)(subclass)
    wrapped = cast("type[serializers.ModelSerializer[Any]]", subclass)
    _component_name_cache[key] = wrapped
    return wrapped


def _ordered_union(*sequences: Sequence[str]) -> tuple[str, ...]:
    """Concatenate ``sequences``, dropping later duplicates, preserving first-seen order — used
    to combine e.g. ``PROFILE_EDITABLE_FIELDS`` and ``PROFILE_READ_FIELDS`` into one deterministic
    field order (``docs/CONTRACT.md`` §5: the union of ``PROFILE_EDITABLE_FIELDS`` and
    ``PROFILE_READ_FIELDS``)."""
    seen: set[str] = set()
    result: list[str] = []
    for sequence in sequences:
        for item in sequence:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return tuple(result)


def _full_field_names(model: type[Model]) -> tuple[str, ...]:
    """Every real field on ``model`` minus :data:`DENIED_FIELDS`, in ``_meta.get_fields()``
    order — the "every real field" shape the admin full-fields accessors below use
    (``docs/CONTRACT.md`` §5: admin GET/PATCH sees every field except ``password``, not just the
    self-service allowlist).

    Deliberately iterates ``model._meta.get_fields()`` directly rather than going through
    :func:`_valid_field_names`'s ``set`` — a ``set``'s iteration order is hash-randomized per
    process (``PYTHONHASHSEED``), which would make the generated field order, and therefore
    :func:`_generated_name`'s digest, churn across process restarts even with identical settings.
    """
    return tuple(
        f.name
        for f in model._meta.get_fields()
        if (
            getattr(f, "concrete", False)
            or (getattr(f, "many_to_many", False) and not getattr(f, "auto_created", False))
        )
        and f.name not in DENIED_FIELDS
    )


# --------------------------------------------------------------------------------- self-service


def get_user_read_serializer() -> type[serializers.ModelSerializer[Any]]:
    """``USER_READ_FIELDS``, entirely read-only — ``GET /me/`` and the admin user-read views.
    Includes locked fields for visibility; none of them writable from here or anywhere else on
    the self-service surface."""
    fields = tuple(conf.get_setting("USER_READ_FIELDS"))
    model = get_user_model()
    _validate_known_fields(model, fields, "USER_READ_FIELDS")
    return _with_component_name(build_serializer(model, fields, read_only_fields=fields), "MeUser")


def get_user_editable_serializer() -> type[serializers.ModelSerializer[Any]]:
    """``USER_EDITABLE_FIELDS`` minus ``USER_LOCKED_FIELDS`` — belt-and-braces even if a host
    lists a locked field in the editable set (``docs/CONTRACT.md`` §6). Currently unused by any
    Phase-5 view (``GET /me/`` is read-only), kept for forward-compat and as the admin PATCH
    allowlist baseline."""
    model = get_user_model()
    locked = frozenset(conf.get_setting("USER_LOCKED_FIELDS"))
    _validate_known_fields(model, locked, "USER_LOCKED_FIELDS")
    fields = tuple(f for f in conf.get_setting("USER_EDITABLE_FIELDS") if f not in locked)
    _validate_known_fields(model, fields, "USER_EDITABLE_FIELDS")
    return build_serializer(model, fields)


def get_user_public_serializer() -> type[serializers.ModelSerializer[Any]]:
    """``USER_PUBLIC_FIELDS``, entirely read-only — the nested ``user`` block on a public profile
    response."""
    fields = tuple(conf.get_setting("USER_PUBLIC_FIELDS"))
    model = get_user_model()
    _validate_known_fields(model, fields, "USER_PUBLIC_FIELDS")
    return _with_component_name(
        build_serializer(model, fields, read_only_fields=fields), "PublicUser"
    )


def get_profile_read_serializer() -> type[serializers.ModelSerializer[Any]]:
    """The union of ``PROFILE_EDITABLE_FIELDS`` and ``PROFILE_READ_FIELDS``, entirely read-only —
    ``GET /me/profile/`` (``docs/CONTRACT.md`` §5)."""
    model = resolution.get_profile_model()
    fields = _ordered_union(
        conf.get_setting("PROFILE_EDITABLE_FIELDS"), conf.get_setting("PROFILE_READ_FIELDS")
    )
    _validate_known_fields(model, fields, "PROFILE_EDITABLE_FIELDS/PROFILE_READ_FIELDS")
    return _with_component_name(
        build_serializer(model, fields, read_only_fields=fields), "MeProfile"
    )


def get_profile_edit_serializer() -> type[serializers.ModelSerializer[Any]]:
    """``PROFILE_EDITABLE_FIELDS``, writable — ``PATCH /me/profile/``."""
    model = resolution.get_profile_model()
    fields = tuple(conf.get_setting("PROFILE_EDITABLE_FIELDS"))
    _validate_known_fields(model, fields, "PROFILE_EDITABLE_FIELDS")
    return _with_component_name(build_serializer(model, fields), "MeProfileUpdate")


_public_profile_cache: dict[
    tuple[type[serializers.ModelSerializer[Any]], type[serializers.ModelSerializer[Any]]],
    type[serializers.ModelSerializer[Any]],
] = {}


def get_public_profile_serializer() -> type[serializers.ModelSerializer[Any]]:
    """``PROFILE_PUBLIC_FIELDS`` plus a nested ``user`` block built from ``USER_PUBLIC_FIELDS``
    (``docs/CONTRACT.md`` §5: ``GET /profiles/``, ``GET /profiles/{id}/``). ``build_serializer()``
    itself takes only field-name strings (its signature is frozen,
    ``docs/CONTRACT.md`` §11), so the nesting is a thin cached subclass built here rather than a
    new factory parameter."""
    model = resolution.get_profile_model()
    fields = _ordered_union(conf.get_setting("PROFILE_PUBLIC_FIELDS"), ("user",))
    _validate_known_fields(model, fields, "PROFILE_PUBLIC_FIELDS")
    base = build_serializer(model, fields, read_only_fields=fields)
    user_serializer = get_user_public_serializer()

    key = (base, user_serializer)
    cached = _public_profile_cache.get(key)
    if cached is not None:
        return cached

    subclass = type(
        f"{base.__name__}WithUser",
        (base,),
        {"user": user_serializer(read_only=True)},
    )
    serializer_cls = _with_component_name(
        cast("type[serializers.ModelSerializer[Any]]", subclass), "PublicProfile"
    )
    _public_profile_cache[key] = serializer_cls
    return serializer_cls


def get_setting_read_serializer() -> type[serializers.ModelSerializer[Any]]:
    """The union of ``SETTING_EDITABLE_FIELDS`` and ``SETTING_READ_FIELDS``, entirely read-only —
    ``GET /me/setting/``."""
    model = resolution.get_setting_model()
    fields = _ordered_union(
        conf.get_setting("SETTING_EDITABLE_FIELDS"), conf.get_setting("SETTING_READ_FIELDS")
    )
    _validate_known_fields(model, fields, "SETTING_EDITABLE_FIELDS/SETTING_READ_FIELDS")
    return _with_component_name(
        build_serializer(model, fields, read_only_fields=fields), "MeSetting"
    )


def get_setting_edit_serializer() -> type[serializers.ModelSerializer[Any]]:
    """``SETTING_EDITABLE_FIELDS``, writable — ``PATCH /me/setting/``."""
    model = resolution.get_setting_model()
    fields = tuple(conf.get_setting("SETTING_EDITABLE_FIELDS"))
    _validate_known_fields(model, fields, "SETTING_EDITABLE_FIELDS")
    return _with_component_name(build_serializer(model, fields), "MeSettingUpdate")


# --------------------------------------------------------------------------------------- admin


def get_admin_user_serializer() -> type[serializers.ModelSerializer[Any]]:
    """Every real field on the resolved user model except ``password`` — the admin surface's
    full-fields read/write serializer (``docs/CONTRACT.md`` §5: admin sees everything except
    ``password``). Fields Django itself marks non-editable (e.g. ``date_joined``) come back
    read-only automatically, via ``ModelSerializer``'s own handling of ``Field.editable`` — no
    explicit ``read_only_fields`` needed here."""
    model = get_user_model()
    return _with_component_name(build_serializer(model, _full_field_names(model)), "AdminUser")


def get_admin_profile_serializer() -> type[serializers.ModelSerializer[Any]]:
    """Every real field on the resolved Profile model, minus :data:`DENIED_FIELDS` — the admin
    full-fields build (``docs/CONTRACT.md`` §5), not ``PROFILE_EDITABLE_FIELDS``.

    ``user`` is read-only here — full-fields would otherwise make the owning O2O writable,
    letting an admin ``PATCH`` re-point one user's Profile row onto another account. Still
    visible on ``GET``, never accepted on ``PATCH``."""
    model = resolution.get_profile_model()
    return _with_component_name(
        build_serializer(model, _full_field_names(model), read_only_fields=("user",)),
        "AdminProfile",
    )


def get_admin_setting_serializer() -> type[serializers.ModelSerializer[Any]]:
    """Every real field on the resolved Setting model, minus :data:`DENIED_FIELDS` — the admin
    full-fields build, not ``SETTING_EDITABLE_FIELDS``. ``user`` is read-only — see
    :func:`get_admin_profile_serializer`'s docstring for why."""
    model = resolution.get_setting_model()
    return _with_component_name(
        build_serializer(model, _full_field_names(model), read_only_fields=("user",)),
        "AdminSetting",
    )


# ------------------------------------------------------------------------------ deletion request


class DeletionRequestCreateSerializer(serializers.ModelSerializer[AccountDeletionRequest]):
    """``POST /me/deletion-request/``'s request body — the only field a caller may supply.

    ``AccountDeletionRequest`` isn't swappable (``docs/CONTRACT.md`` §1), and this shape isn't a
    settings-driven allowlist surface, so it's hand-written with an explicit field list rather
    than routed through :func:`build_serializer` — exactly the case this module's own docstring
    and the Phase 5 guide call out.
    """

    class Meta:
        model = AccountDeletionRequest
        fields: ClassVar[list[str]] = ["reason"]
        extra_kwargs: ClassVar[dict[str, dict[str, Any]]] = {
            "reason": {"required": False, "allow_blank": True}
        }


class DeletionRequestSerializer(serializers.ModelSerializer[AccountDeletionRequest]):
    """``GET``/``POST`` responses on ``/me/deletion-request/`` — entirely read-only.

    Deliberately excludes ``user`` (redundant — the caller already knows who they are) and
    ``reviewed_by`` — never expose ``reviewed_by`` on any user-facing serializer, per this
    package's own rules and the Phase 5 guide.
    """

    class Meta:
        model = AccountDeletionRequest
        fields: ClassVar[list[str]] = [
            "id",
            "status",
            "reason",
            "requested_at",
            "reviewed_at",
            "finalize_at",
        ]
        read_only_fields = fields


# ------------------------------------------------------------------------------------- admin API


class AdminDeletionRequestSerializer(serializers.ModelSerializer[AccountDeletionRequest]):
    """``GET /deletion-requests/``, and the response body of the review/finalize actions —
    entirely read-only. Unlike the self-service :class:`DeletionRequestSerializer`, this one
    includes ``user`` and ``reviewed_by`` — an admin reviewing a queue of everyone's requests
    needs to know whose request it is and who already reviewed it; a self-service caller already
    knows both (or, for ``reviewed_by``, was never meant to see it, per this package's own
    rules)."""

    class Meta:
        model = AccountDeletionRequest
        fields: ClassVar[list[str]] = [
            "id",
            "user",
            "status",
            "reason",
            "requested_at",
            "reviewed_at",
            "reviewed_by",
            "finalize_at",
        ]
        read_only_fields = fields


class DeletionReviewSerializer(serializers.Serializer[Any]):
    """``POST /deletion-requests/{id}/review/``'s request body — the only field a caller may
    supply. Not a ``ModelSerializer``: ``approved`` isn't itself a model field, it's the input to
    ``DeletionService.review()``'s ``approved`` kwarg."""

    approved = serializers.BooleanField(required=True)


class AdminDeletionRequestFilterSerializer(serializers.Serializer[Any]):
    """Validates ``GET /deletion-requests/``'s query params before they ever reach a
    ``.filter()`` call — fed to ``appkit.validation.validate_query_params``, per this package's
    own "never raw ``**request.GET``" rule. An invalid ``status`` is a clean ``400`` through
    appkit's envelope, not a query that silently returns an empty page."""

    status = serializers.ChoiceField(choices=AccountDeletionRequest.Status.choices, required=False)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)


class AdminUserFilterSerializer(serializers.Serializer[Any]):
    """Validates ``GET /`` (the admin user list)'s pagination query params. The *filterable*
    field names themselves come from the resolved user model at request time
    (``admin_views._filterable_user_fields``), never a static list here — a host's subclassed
    field must be filterable with zero package changes, which a serializer enumerating field
    names statically could never provide."""

    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)
