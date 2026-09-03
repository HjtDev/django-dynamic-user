# CONTRACT.md — django-dynamic-user

The frozen public contract for `django-dynamic-user` (module: `dynamic_user`). Every later build
phase (`docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md` §2) implements exactly what's written here —
it does not re-derive model shapes, signal payloads, service signatures, endpoints, settings, or
hooks. If code and this file ever disagree, that disagreement is a bug in one of them, not a
license to improvise (`docs/APP-DESIGN.md` §11).

**Sources checked while writing this**, not assumed from the guide's prose:
`hjtdev-appkit` 2.0.2's actual installed source
(`appkit/{permissions,pagination,mixins,cache,throttling,validation,files,media,net,text}.py`,
`appkit/backend/pyproject.toml`'s `[project.optional-dependencies]`, `appkit/frontend/src/index.ts`)
and `hjtdev-django-cleanup`'s own `docs/CONTRACT.md` as the shape precedent for this document
(numbered `§`-sections, a deviations register, an explicit "Requires another app package" line
closing each model/logic section). Every appkit symbol and extra named below was read from that
source, not recalled from documentation — one finding from that reading changed a decision
`docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md` §1 states as settled; see §10 item 1.

This app is **the data layer only** — no registration, login, JWT, or password reset. Those
belong to a future, separate `auth-app` package reaching this one only through
`get_user_model()`.

---

## §0. Identity & boundary

| | |
|---|---|
| Importable module | `dynamic_user` |
| PyPI distribution | `django-dynamic-user` |
| npm package | `@hjtdev/django-dynamic-user` |
| GitHub repo | `HjtDev/django-dynamic-user` |
| Declared dependencies (not app packages, `APP-DESIGN.md` §1.1's named exception) | `hjtdev-appkit>=2.0,<3.0` |
| Ships-with-Django exception | `django.contrib.contenttypes` — used only by `HistoryMixin`/`ChangeLogEntry` (§1). Not a §6 boundary concern. |
| Scope | Data layer only. `User`/`Profile`/`Setting` models, self-service + admin DRF surfaces, a Jazzmin-compatible admin, an opt-out account-deletion review flow, a mixin library, a settings-driven serializer factory, frontend hooks for both surfaces. **No** registration, login, JWT, or password reset. |
| Model strategy | Swappable concrete defaults, mirroring `django.contrib.auth` exactly — see §1. |
| Two frontend basePath keys | `dynamic_user` → `/api/v1/users` (self-service), `dynamic_user_admin` → `/api/v1/admin/users` (admin) |
| Admin gating | `appkit.permissions.IsAppAdmin` (`is_staff`) by default; `DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]=True` tightens every admin gate to `is_superuser`. **Unconditionally, regardless of that switch:** only an actual superuser may write `is_staff`/`is_superuser`/`is_active`/`groups`/`user_permissions` on any user (§5). |
| Jazzmin | **Not a dependency.** This app registers plain `django.contrib.admin.ModelAdmin` classes; a host's own installed Jazzmin renders them. The README suggests `JAZZMIN_SETTINGS["icons"]` entries; this package never writes to that dict itself (`APP-DESIGN.md` §5). |

**The three rails every phase from here on is checked against** (`CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md` §0):

1. Every model reference is indirect: `settings.AUTH_USER_MODEL` for the user;
   `dynamic_user.resolution.get_profile_model()`/`get_setting_model()` for the other two. Never
   `from dynamic_user.models import User/Profile/Setting` anywhere in this package's own code.
2. A settings change never produces a migration diff. The one sanctioned exception, forced by
   Django itself: `USERNAME_FIELD`/`REQUIRED_FIELDS` as class attributes on the abstract user base
   (§1) — a one-time, pre-`migrate` host decision, not a runtime setting.
3. No serializer on any surface ever emits `password` or a hash. No code path reachable by a
   non-superuser — including a user's own self-service request — may write `is_staff`,
   `is_superuser`, `is_active`, `groups`, or `user_permissions` on any user (§5 extends the guide's
   three-field list to five; see §10 item 8). A public profile response exposes exactly the
   settings-declared allowlist intersected with the resolved model's real fields, never
   `fields = "__all__"`.

---

## §1. Models

Every FK/O2O-shaped reference to a user is `settings.AUTH_USER_MODEL` — including
`AccountDeletionRequest.user`/`.reviewed_by`, despite living in the same `models.py` as `User`
itself. **Requires another app package: No** (`django.contrib.contenttypes` only, for
`HistoryMixin`).

### `AbstractDynamicUser` + concrete `User`

```python
# dynamic_user/models.py
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class AbstractDynamicUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # is_superuser, groups, user_permissions come from PermissionsMixin — not redeclared here.

    objects = UserManager()

    # The ONE sanctioned exception to "no settings-affecting class attribute" (§0 item 2 above,
    # CLAUDE.md rule 2). Django's auth machinery reads these at class-definition time, not
    # request time — changing them is a schema-affecting decision a host makes once, before its
    # first `migrate`, never a DYNAMIC_USER setting.
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
        ]


class User(AbstractDynamicUser):
    class Meta(AbstractDynamicUser.Meta):
        swappable = "AUTH_USER_MODEL"
```

**Addition to flag (§10 item 3):** `managers.py`'s `UserManager(BaseUserManager)` —
`create_user(username, email, password=None, **extra)` and
`create_superuser(username, email, password, **extra)`. `AbstractBaseUser` requires a manager
and the guide's Phase 0 item 1 doesn't mention one; omitting it isn't an option. `create_superuser`
sets `is_staff=True, is_superuser=True` directly — this is the one place in the whole package
those fields are written outside a superuser-gated HTTP path, and it's safe *because* it has no
HTTP path at all: it's reachable only from `createsuperuser`/a shell/a data migration, never a
request. Documented here so Phase 2 doesn't read it as a violation of §0 item 3.

### `AbstractProfile` + concrete `Profile`

```python
class AbstractProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    bio = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Profile(AbstractProfile):
    class Meta(AbstractProfile.Meta):
        swappable = "DYNAMIC_USER_PROFILE_MODEL"
```

**No avatar field on `AbstractProfile` — decision recorded, §10 item 4.** `AvatarMixin` (below)
is opt-in, composed by a host that wants one: `class Profile(AbstractProfile, AvatarMixin)`. An
`ImageField` hard-requires Pillow (`fields.E210` at `manage.py check` without it); baking one into
the default `Profile` would make the `[avatar]` extra a de facto hard dependency for every host,
contradicting §0's "declared, optional extra" framing.

### `AbstractSetting` + concrete `Setting`

```python
class AbstractSetting(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="setting"
    )
    language = models.CharField(max_length=10, default="en")
    timezone = models.CharField(max_length=64, default="UTC")
    notifications_enabled = models.BooleanField(default=True)

    class Meta:
        abstract = True


class Setting(AbstractSetting):
    class Meta(AbstractSetting.Meta):
        swappable = "DYNAMIC_USER_SETTING_MODEL"
```

Deliberately minimal — a host's own subclass is where project-specific preferences go
(`CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md` §2 Phase 0 prompt item 1).

### `AccountDeletionRequest`

```python
class AccountDeletionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"
        FINALIZED = "finalized"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deletion_requests"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_deletion_requests",
    )
    finalize_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "finalize_at"]),
            models.Index(fields=["user", "status"]),
        ]
```

Not swappable — a host extending this shape is expected to be rare enough that §6/§7's
`DYNAMIC_USER` settings already cover it (grace period, deletion mode); no
`DYNAMIC_USER_DELETION_REQUEST_MODEL` is introduced.

### Mixins — `mixins.py`

One composable abstract model per mixin, each documenting exactly which fields it adds and any
requirement it places on the composing model.

```python
class AvatarMixin(models.Model):
    """Adds an avatar. Needs the [avatar] extra (Pillow, via hjtdev-appkit[images]) only if the
    composing model is actually used — this mixin's own import never requires Pillow to be
    installed; only saving/validating an uploaded file does, via appkit.files.validate_image."""
    avatar = models.ImageField(upload_to="dynamic_user/avatars/", blank=True, null=True)
    avatar_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    """Adds created_at/updated_at. No Meta requirement on the composing model."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class HistoryMixin(models.Model):
    """Adds nothing to the composing model's own fields — provides a `.log_change(field, old,
    new, *, actor=None)` manager-adjacent method that writes a ChangeLogEntry row via a
    GenericForeignKey. The ONLY place this package touches contenttypes. The composing model
    needs no extra Meta; ChangeLogEntry itself is a concrete, always-migrated model (not
    swappable — a generic log table has no reason to vary per host)."""

    class Meta:
        abstract = True


class ChangeLogEntry(models.Model):
    content_type = models.ForeignKey("contenttypes.ContentType", on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["content_type", "object_id"])]


class SoftDeleteMixin(models.Model):
    """Adds is_deleted, deleted_at. Requirement on the composing model, stated explicitly because
    it cannot be auto-provided by the mixin: the composing model must define its own `objects`
    (filtered to is_deleted=False) and `all_objects` (unfiltered) managers — a mixin cannot
    safely inject a manager onto User, since User already needs UserManager for
    AbstractBaseUser's own machinery, and Django resolves exactly one default manager."""
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class VerificationMixin(models.Model):
    """Flags + timestamps only — no delivery logic. Sending a verification code is an auth-app's
    or host's job; this mixin just gives it somewhere to record the result."""
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified = models.BooleanField(default=False)
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class LastSeenMixin(models.Model):
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        abstract = True


class MetadataMixin(models.Model):
    """A JSONField escape hatch for host-specific, unstructured data that doesn't warrant a
    real column. Never read or written by this package's own views/serializers by default —
    a host opts a field allowlist into it explicitly."""
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True
```

---

## §2. Resolution — `resolution.py`

```python
def get_profile_model() -> type[models.Model]: ...
def get_setting_model() -> type[models.Model]: ...
def get_profile_model_string() -> str: ...
def get_setting_model_string() -> str: ...
```

Mirrors `django.contrib.auth.get_user_model()`: reads `settings.DYNAMIC_USER_PROFILE_MODEL` /
`DYNAMIC_USER_SETTING_MODEL`, resolves via `django.apps.apps.get_model(..., require_ready=False)`,
raises `django.core.core.exceptions.ImproperlyConfigured` naming the exact misconfigured setting
(e.g. `"DYNAMIC_USER_PROFILE_MODEL must be of the form 'app_label.ModelName'"` /
`"DYNAMIC_USER_PROFILE_MODEL refers to model 'x.Y' that has not been installed"`) — never a bare
`AttributeError`/`LookupError`. Caching follows Django's own app-registry lifecycle (keyed through
`apps.get_model`'s own caching, not a hand-rolled module-level dict) so it stays correct across a
test suite's database teardown/rebuild between test modules.

**Requires another app package: No.**

---

## §3. Signals — `signals.py`

Every payload is a bare ID or primitive — never a model instance — so a host's `core/signals.py`
receiver never needs this app's models imported just to read an event
(`APP-DESIGN.md` §6's minimality rule).

```python
import django.dispatch

profile_created = django.dispatch.Signal()
"""Sent after Profile auto-provisioning creates a row. sender=get_profile_model().
Payload: user_id: int"""

setting_created = django.dispatch.Signal()
"""Sent after Setting auto-provisioning creates a row. sender=get_setting_model().
Payload: user_id: int"""

deletion_requested = django.dispatch.Signal()
"""Sent by DeletionService.request(). sender=AccountDeletionRequest.
Payload: user_id: int, request_id: int, finalize_at: datetime"""

deletion_reviewed = django.dispatch.Signal()
"""Sent by DeletionService.review(). sender=AccountDeletionRequest.
Payload: request_id: int, status: str, reviewed_by_id: int | None"""

deletion_finalized = django.dispatch.Signal()
"""Sent by DeletionService.finalize(), AFTER the row/user mutation, but with user_id captured
BEFORE a hard_delete removes the row. sender=AccountDeletionRequest.
Payload: user_id: int, mode: str"""

profile_updated = django.dispatch.Signal()
"""Sent by ProfileService.update() when at least one field actually changed. sender=get_profile_model().
Payload: user_id: int, changed_fields: list[str]"""
```

**Minimality argument, per field:**

- `profile_created`/`setting_created` carry only `user_id` — everything else about the new row is
  one `get_profile_model().objects.get(user_id=...)` away, and neither name is stable enough
  across a host's subclass to belong in a fixed payload.
- `deletion_requested` carries `request_id` (so a receiver can act without a query) and
  `finalize_at` (the one piece of information genuinely time-sensitive enough to be worth
  avoiding a round-trip for — a notification-app deciding *when* to remind the user needs it
  immediately). `reason` is omitted: free text, exactly the kind of field a fixed payload
  shouldn't couple to.
- `deletion_reviewed` carries `status` (`approved`/`rejected`) and `reviewed_by_id` (who decided)
  — the two facts a notification receiver needs to compose "your request was approved/rejected by
  X" without a query.
- `deletion_finalized` carries `mode` (`hard_delete`/`anonymize`) because a receiver's correct
  behavior genuinely differs by mode (e.g. whether it's still safe to look the user up at all) —
  and `user_id`, since after `hard_delete` there is no row left to query it from.
- `profile_updated` carries `changed_fields` (not old/new values) — enough for a receiver to
  decide *whether* it cares (e.g. "did bio change?") without this package needing to serialize
  arbitrary before/after values of fields it doesn't control the shape of (a host's subclass may
  add fields of any type).

`sender` for `profile_created`/`setting_created`/`profile_updated` is the *resolved* class
(`get_profile_model()`/`get_setting_model()`, evaluated at signal-send time, not import time) so a
host can filter with `@receiver(profile_created, sender=get_profile_model())` even against a
swapped model. `AccountDeletionRequest` is not swappable, so naming it concretely as `sender` for
the three deletion signals is safe.

**Requires another app package: No.**

---

## §4. `services.py`

Users are typed as `django.contrib.auth.base_user.AbstractBaseUser` (Django core, not a concrete
`User` import). Profile/Setting return types are `AbstractProfile`/`AbstractSetting` — accurate
for any resolved model, and import-safe because importing the *abstract base* from
`dynamic_user.models` is not importing a concrete swappable model (**refinement of the Phase 0
prompt's `-> Profile`/`-> Setting`, flagged in §10 item 5**).

```python
from datetime import datetime
from django.contrib.auth.base_user import AbstractBaseUser

from .models import AbstractProfile, AbstractSetting, AccountDeletionRequest


class DeletionRequestAlreadyExists(Exception):
    """Raised by DeletionService.request() when the user already has a pending or approved
    request. Views map this to HTTP 409 (§5)."""


class InvalidDeletionState(Exception):
    """Raised by DeletionService.review()/.finalize()/.cancel() when called against a request
    not in the required status. Views map this to HTTP 409 (§5)."""


class ProfileService:
    @staticmethod
    def update(user: AbstractBaseUser, validated_data: dict) -> AbstractProfile:
        """Writes validated_data onto user's Profile (get_profile_model()), sends
        profile_updated with changed_fields if anything actually changed. No-op fields (equal to
        current value) are excluded from changed_fields."""
        ...


class SettingService:
    @staticmethod
    def update(user: AbstractBaseUser, validated_data: dict) -> AbstractSetting:
        """Writes validated_data onto user's Setting (get_setting_model()). No signal — Setting
        changes are not currently part of the versioned-contract surface (§11 open item)."""
        ...


class DeletionService:
    @staticmethod
    def request(user: AbstractBaseUser, *, reason: str = "") -> AccountDeletionRequest:
        """Raises DeletionRequestAlreadyExists if a pending or approved request already exists
        for this user. Computes finalize_at = now() + DELETION_GRACE_PERIOD_DAYS, creates the
        row with status=PENDING, sends deletion_requested."""
        ...

    @staticmethod
    def review(
        request_id: int, *, approved: bool, reviewed_by: AbstractBaseUser
    ) -> AccountDeletionRequest:
        """Raises InvalidDeletionState if the request is not currently PENDING. Moves it to
        APPROVED or REJECTED, stamps reviewed_at/reviewed_by, sends deletion_reviewed. Rejecting
        is terminal — a rejected request cannot later be approved; the user must call .request()
        again."""
        ...

    @staticmethod
    def finalize(request_id: int) -> None:
        """Raises InvalidDeletionState if the request is not currently APPROVED. Implements
        DYNAMIC_USER["DELETION_MODE"]: "hard_delete" deletes the user row (Profile/Setting/this
        request cascade per their own on_delete); "anonymize" calls the conf-resolved anonymize
        function instead and sets this request's own status to FINALIZED (nothing to cascade-
        delete in this mode). Sends deletion_finalized with mode either way, user_id captured
        before any delete."""
        ...

    @staticmethod
    def cancel(user: AbstractBaseUser) -> None:
        """Raises InvalidDeletionState if the user's current request is not PENDING (already
        approved/rejected/finalized, or no request exists at all)."""
        ...
```

**Requires another app package: No.**

---

## §5. Endpoints

### Self-service — `urls.py`, basePath `/api/v1/users`

All throttle scopes are **literal strings** (see §10 item 1 for why `appkit.throttling
.throttle_scope()` cannot be used here), `dynamic_user_`-prefixed, tagged `["dynamic-user"]`.

| Method | Path | Permission | Throttle scope | Request | Response |
|---|---|---|---|---|---|
| `GET` | `/me/` | `IsAuthenticated` | `dynamic_user_me` | — | `USER_READ_FIELDS` serializer (read-only) — includes locked fields for visibility, none writable from here or anywhere else on this surface |
| `GET` | `/me/profile/` | `IsAuthenticated` | `dynamic_user_me` | — | `PROFILE_EDITABLE_FIELDS ∪ PROFILE_READ_FIELDS` serializer, read |
| `PATCH` | `/me/profile/` | `IsAuthenticated`, `IsProfileOwner` | `dynamic_user_profile_update` | `PROFILE_EDITABLE_FIELDS` subset | Updated profile via `ProfileService.update` |
| `GET` | `/me/setting/` | `IsAuthenticated` | `dynamic_user_me` | — | `SETTING_EDITABLE_FIELDS ∪ SETTING_READ_FIELDS` serializer, read |
| `PATCH` | `/me/setting/` | `IsAuthenticated`, `IsProfileOwner` | `dynamic_user_setting_update` | `SETTING_EDITABLE_FIELDS` subset | Updated setting via `SettingService.update` |
| `GET` | `/profiles/` | `IsAuthenticated` | `dynamic_user_profiles_list` | query: `page`, `page_size` | Paginated (`appkit.pagination.DefaultPagination`, `appkit.mixins.CachedListMixin`, `cache_namespace="dynamic_user"`); queryset filtered `is_public=True`; `PROFILE_PUBLIC_FIELDS` serializer with a nested `user` block from `USER_PUBLIC_FIELDS` |
| `GET` | `/profiles/{id}/` | `IsAuthenticated`, `IsPublicOrOwner` | `dynamic_user_profile_retrieve` | — | Same shape as above for one profile. **`{id}` is the target user's id, not the Profile row's own pk** — flagged in §10 item 6. `404` (not `403`) when private and requester isn't the owner |
| `POST` | `/me/deletion-request/` | `IsAuthenticated` | `dynamic_user_deletion_request` | `{"reason": str}` (optional) | `201` with the created request, or `409` (`DeletionRequestAlreadyExists`) if one is already pending/approved |
| `GET` | `/me/deletion-request/` | `IsAuthenticated` | `dynamic_user_deletion_request` | — | The caller's current request, or `404` if none exists |
| `DELETE` | `/me/deletion-request/` | `IsAuthenticated` | `dynamic_user_deletion_request` | — | `204` via `DeletionService.cancel`; `409` (`InvalidDeletionState`) if not currently pending |

Every object on this surface is resolved from `request.user` — never a URL-supplied id — except
`GET /profiles/{id}/`, whose entire purpose is looking up *someone else's* public data; that view
is the one place on this surface an id is accepted, and it is read-only.

### Admin — `urls_admin.py`, basePath `/api/v1/admin/users`

**Paths collapse to the basePath root — `/api/v1/admin/users/42/`, not
`.../users/users/42/`** (refinement of the Phase 0 prompt's literal `/users/{id}/` shape under an
already-`/users`-suffixed basePath; flagged in §10 item 7). All gated by the admin-gate wrapper
(§6), tagged `["dynamic-user-admin"]`.

| Method | Path | Extra gate | Throttle scope | Request | Response |
|---|---|---|---|---|---|
| `GET` | `/` | — | `dynamic_user_admin_users_list` | query: filters via `appkit.validation.validate_query_params`/`safe_filter_kwargs` | Paginated (`appkit.pagination.DefaultPagination`), full `USER_READ_FIELDS` (admin sees everything except `password`) |
| `GET` | `/{id}/` | — | `dynamic_user_admin_user_retrieve` | — | Single user, full fields except `password` |
| `PATCH` | `/{id}/` | `CanEscalatePrivilege` | `dynamic_user_admin_user_update` | Any user field except `password` | See gate rule below. `403` (whole request rejected) if a non-superuser's body touches a gated field |
| `GET` | `/{id}/profile/` | — | `dynamic_user_admin_profile_update` | — | Every real field on the resolved Profile model (full-fields `build_serializer()` call, not `PROFILE_EDITABLE_FIELDS`) |
| `PATCH` | `/{id}/profile/` | — | `dynamic_user_admin_profile_update` | Any Profile field | Updated via `ProfileService.update(target_user, ...)` |
| `GET` | `/{id}/setting/` | — | `dynamic_user_admin_setting_update` | — | Every real field on the resolved Setting model |
| `PATCH` | `/{id}/setting/` | — | `dynamic_user_admin_setting_update` | Any Setting field | Updated via `SettingService.update(target_user, ...)` |
| `GET` | `/deletion-requests/` | — | `dynamic_user_admin_deletions_list` | query: `status` filter | Paginated `AccountDeletionRequest` list |
| `POST` | `/deletion-requests/{id}/review/` | — | `dynamic_user_admin_deletion_review` | `{"approved": bool}` | `DeletionService.review(request_id, approved=..., reviewed_by=request.user)` |
| `POST` | `/deletion-requests/{id}/finalize/` | **superuser-only, always** | `dynamic_user_admin_deletion_finalize` | — | `DeletionService.finalize(request_id)`, bypassing `finalize_at`. `403` for any non-superuser regardless of `ADMIN_REQUIRES_SUPERUSER` |

**The privilege-escalation gate, spelled out explicitly so it cannot be implemented as "any staff
user can PATCH anything":**

- The **general admin gate** (call it `IsDynamicUserAdmin`, one wrapper class) resolves
  `DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]` once: `False` (default) → behaves like
  `appkit.permissions.IsAppAdmin` (`is_staff`); `True` → requires `is_superuser`. Every admin view
  imports and uses this wrapper, never `appkit.permissions.IsAppAdmin` directly — routing every
  view through one place is what makes the setting actually apply everywhere.
- **`CanEscalatePrivilege` is a second, independent permission that runs only on `PATCH
  /{id}/` and is never controlled by `ADMIN_REQUIRES_SUPERUSER`.** It inspects the request body
  for the exact key set **`{"is_active", "is_staff", "is_superuser", "groups",
  "user_permissions"}`** (§10 item 8 flags `groups`/`user_permissions` as an extension beyond the
  guide's three-field list — leaving them ungated would let a staff admin hand themselves
  superuser-equivalent permissions through a permission object instead of the flag itself). If the
  body touches **any** key in that set and `request.user.is_superuser` is not `True`, the entire
  request is rejected with **`403`** — not a silent per-field drop. A caller gets an honest
  "you may not set these fields" error instead of a response that looks like it succeeded but
  quietly changed less than it asked for.
- This check runs **before** the view touches any field, and it runs whether or not the general
  admin gate above already required superuser — i.e. even under `ADMIN_REQUIRES_SUPERUSER=True`,
  the code path is still present and still tested, since the setting could change under it later.
- `password` is excluded from every serializer this endpoint can produce or accept, unconditionally
  (`build_serializer`'s hard deny-list, §4 of `APP-DESIGN.md`, formalized in the guide's Phase 4).
- `POST /deletion-requests/{id}/finalize/` is superuser-only **regardless of
  `ADMIN_REQUIRES_SUPERUSER`**, because it is a genuinely irreversible action (bypasses the grace
  period entirely) that a staff-level admin dashboard should never be able to trigger by accident
  or by a compromised staff account — a stricter floor than the general admin gate, not something
  the setting can loosen.

**Requires another app package: No.**

---

## §6. Settings — `DYNAMIC_USER` dict, → `conf.py` `DEFAULTS`

Plus **two top-level** settings, alongside `AUTH_USER_MODEL`, not `DYNAMIC_USER` keys — because
Django's `swappable_dependency()` machinery expects a top-level setting name:

| Setting | Meaning |
|---|---|
| `DYNAMIC_USER_PROFILE_MODEL` | `"app_label.ModelName"`, defaults to `"dynamic_user.Profile"` if unset — but a host is expected to set it explicitly (`resolution.py`/`checks.py` validate it either way) |
| `DYNAMIC_USER_SETTING_MODEL` | Same, defaults to `"dynamic_user.Setting"` |

### `DYNAMIC_USER` dict

| Key | Default | Meaning |
|---|---|---|
| `USER_READ_FIELDS` | `["id", "username", "name", "email", "phone", "is_active", "date_joined"]` | Fields on `GET /me/` and the admin user read views (admin gets the full model regardless via a separate full-fields build, see §5) |
| `USER_EDITABLE_FIELDS` | `["name", "phone"]` | Fields writable via a *future* self-service `/me/` PATCH — currently unused since `GET /me/` is read-only per §5, kept for forward-compat and admin PATCH's own allowlist baseline |
| `USER_LOCKED_FIELDS` | `["username", "email", "is_staff", "is_superuser", "is_active"]` | Subtracted from `USER_EDITABLE_FIELDS` at build time even if a host also lists one of these there — belt-and-braces, deterministic |
| `USER_PUBLIC_FIELDS` | `["id", "username"]` | Fields on the nested `user` block of a public profile response (§5's `/profiles/`, `/profiles/{id}/`) |
| `USER_PRIVILEGED_FIELDS` | `["is_staff", "is_superuser", "is_active", "groups", "user_permissions"]` | The exact set `CanEscalatePrivilege` (§5) gates. A host may **add** to this set via `DYNAMIC_USER["USER_PRIVILEGED_FIELDS"]` but the resolved value is always `DEFAULT ∪ host's` — the floor above can never be shrunk |
| `PROFILE_READ_FIELDS` | `["id", "bio", "is_public"]` | Fields on `GET /me/profile/` |
| `PROFILE_EDITABLE_FIELDS` | `["bio", "is_public"]` | Fields on `PATCH /me/profile/` |
| `PROFILE_PUBLIC_FIELDS` | `["id", "bio"]` | Fields on `/profiles/`, `/profiles/{id}/` — deliberately minimal, see §10 item 2 |
| `SETTING_READ_FIELDS` | `["id", "language", "timezone", "notifications_enabled"]` | Fields on `GET /me/setting/` |
| `SETTING_EDITABLE_FIELDS` | `["language", "timezone", "notifications_enabled"]` | Fields on `PATCH /me/setting/` |
| `PHONE_VALIDATORS` | `[]` | Dotted callable paths, resolved lazily and cached on first use by `validators.run_validators("PHONE_VALIDATORS", value)`. Empty = no extra validation beyond Django's own field checks — no opinionated phone format shipped |
| `NAME_VALIDATORS` | `[]` | Same shape, for `name` |
| `ADMIN_REQUIRES_SUPERUSER` | `False` | `True` tightens every admin gate from `is_staff` to `is_superuser`. Never loosens `CanEscalatePrivilege` or the deletion-finalize gate (§5) |
| `AUTO_CREATE_PROFILE` | `True` | Connects the `User` `post_save(created=True)` receiver that calls `get_profile_model().objects.get_or_create(user=instance)` and sends `profile_created` |
| `AUTO_CREATE_SETTING` | `True` | Same, for Setting/`setting_created` |
| `DELETION_MODE` | `"hard_delete"` | `"hard_delete"` or `"anonymize"` |
| `DELETION_GRACE_PERIOD_DAYS` | `14` | `finalize_at = requested_at + this many days` at `DeletionService.request()` time |
| `DELETION_ANONYMIZE_FUNCTION` | `None` | Dotted path to a callable `(user) -> None`, called by `.finalize()` when `DELETION_MODE="anonymize"`. `None` while `DELETION_MODE="anonymize"` is `ImproperlyConfigured` at check time — fails closed, never silently falls back to hard-delete |
| `DELETION_HISTORY_RETENTION_DAYS` | `90` | Default window `tasks.purge_deletion_history` uses when not passed an explicit `older_than_days` |
| `LAST_SEEN_UPDATE_SECONDS` | `300` | Minimum interval `LastSeenMixin`'s update path (a host-wired hook, not a view this package ships) writes a new `last_seen_at`, to avoid a write per request |

**Field-allowlist ↔ model resolution rule (decision confirmed with the user, §10 item 9):** a
name in any `*_FIELDS` list that doesn't exist on the *resolved* model (via `resolution.py`, never
a hardcoded default) is caught at **startup**, not mid-request, by two cooperating mechanisms:

1. A Django system check (`dynamic_user.E005`) run from `apps.py`'s `ready()`, validating every
   configured allowlist against `get_profile_model()`/`get_setting_model()`/the resolved user
   model at `manage.py check` time, naming the offending field and setting key.
2. `serializers.build_serializer()` (Phase 4) raises `ImproperlyConfigured` with the same message
   shape if it's ever called before/without that check having run (e.g. from a management command
   that skips checks).

This is "degrade gracefully, not 500" read as *a named error at boot, never a silent drop and
never a request-time crash* — reconciling the Phase 0 prompt's "degrade gracefully" language with
the Phase 4 prompt's "raise `ImproperlyConfigured`" and `CLAUDE.md` rule 3's "intersected with the
resolved model's real fields." A default allowlist can never be the one that's missing, since
`checks.py` already requires every swapped model to subclass this package's own abstract base —
only a host-authored addition to an allowlist can trigger `E005`.

No `.env` keys — required or optional. This app configures entirely through `DYNAMIC_USER` plus
the two top-level swappable-model settings.

**Requires another app package: No.**

---

## §7. Frontend hooks

`dynamicUserKeys` (self-service, root `["dynamic_user"]`) and `dynamicUserAdminKeys` (admin, root
`["dynamic_user_admin"]`) are two separate factories — a mutation invalidates only its own
surface's keys. **Cross-surface invalidation decision:** an admin `PATCH` to a user's
profile/setting invalidates only `dynamicUserAdminKeys`, never the self-service surface — an
admin editing user 42 has no reason to bust the *current operator's own* self-service cache, and
there is no reliable way to target "that other user's session" from a mutation's own
`onSuccess` anyway.

### Self-service

| Hook | Wraps | Query key | Invalidation |
|---|---|---|---|
| `useMe()` | `GET /me/` | `dynamicUserKeys.me()` | — (query) |
| `useMyProfile()` | `GET /me/profile/` | `dynamicUserKeys.myProfile()` | — (query) |
| `useUpdateMyProfile()` | `PATCH /me/profile/` | — (mutation) | `dynamicUserKeys.myProfile()` |
| `useMySetting()` | `GET /me/setting/` | `dynamicUserKeys.mySetting()` | — (query) |
| `useUpdateMySetting()` | `PATCH /me/setting/` | — (mutation) | `dynamicUserKeys.mySetting()` |
| `usePublicProfiles(params)` | `GET /profiles/` | `dynamicUserKeys.publicProfiles(params)` | — (query) |
| `usePublicProfile(id)` | `GET /profiles/{id}/` | `dynamicUserKeys.publicProfile(id)` | — (query) |
| `useMyDeletionRequest()` | `GET /me/deletion-request/` | `dynamicUserKeys.myDeletionRequest()` | — (query) |
| `useRequestDeletion()` | `POST /me/deletion-request/` | — (mutation, **never fires on mount**) | `dynamicUserKeys.myDeletionRequest()` |
| `useCancelDeletionRequest()` | `DELETE /me/deletion-request/` | — (mutation, **never fires on mount**) | `dynamicUserKeys.myDeletionRequest()` |

### Admin

| Hook | Wraps | Query key | Invalidation |
|---|---|---|---|
| `useAdminUsers(params)` | `GET /` | `dynamicUserAdminKeys.users(params)` | — (query) |
| `useAdminUser(id)` | `GET /{id}/` | `dynamicUserAdminKeys.user(id)` | — (query) |
| `useUpdateAdminUser(id)` | `PATCH /{id}/` | — (mutation, **never fires on mount**) | `dynamicUserAdminKeys.user(id)`, `dynamicUserAdminKeys.users()` |
| `useAdminUserProfile(id)` | `GET /{id}/profile/` | `dynamicUserAdminKeys.userProfile(id)` | — (query) |
| `useUpdateAdminUserProfile(id)` | `PATCH /{id}/profile/` | — (mutation) | `dynamicUserAdminKeys.userProfile(id)` |
| `useAdminUserSetting(id)` | `GET /{id}/setting/` | `dynamicUserAdminKeys.userSetting(id)` | — (query) |
| `useUpdateAdminUserSetting(id)` | `PATCH /{id}/setting/` | — (mutation) | `dynamicUserAdminKeys.userSetting(id)` |
| `useAdminDeletionRequests(params)` | `GET /deletion-requests/` | `dynamicUserAdminKeys.deletionRequests(params)` | — (query) |
| `useReviewDeletionRequest()` | `POST /deletion-requests/{id}/review/` | — (mutation, **never fires on mount**) | `dynamicUserAdminKeys.deletionRequests()`, `dynamicUserAdminKeys.deletionRequest(id)` |
| `useFinalizeDeletionRequest()` | `POST /deletion-requests/{id}/finalize/` | — (mutation, **never fires on mount**) | `dynamicUserAdminKeys.deletionRequests()`, `dynamicUserAdminKeys.deletionRequest(id)` |

**Addition to flag (§10 item 10):** `useUpdateAdminUserProfile(id)`/`useUpdateAdminUserSetting(id)`
are named distinctly from the guide's shared `useAdminUserProfile(id)`/`useAdminUserSetting(id)`
list, which names one hook per resource without separating read from write — kept as two hooks per
resource (query + mutation) for consistency with every other resource in this table, where the
read/write split is already two hooks (`useMyProfile`/`useUpdateMyProfile`, etc.). No behavior in
the guide's list is dropped, only named precisely.

Both key factories, exported from `index.ts`:

```ts
export const dynamicUserKeys = {
  all: ["dynamic_user"] as const,
  me: () => [...dynamicUserKeys.all, "me"] as const,
  myProfile: () => [...dynamicUserKeys.all, "profile"] as const,
  mySetting: () => [...dynamicUserKeys.all, "setting"] as const,
  publicProfiles: (params?: PublicProfilesParams) =>
    [...dynamicUserKeys.all, "profiles", params] as const,
  publicProfile: (id: number) => [...dynamicUserKeys.all, "profiles", id] as const,
  myDeletionRequest: () => [...dynamicUserKeys.all, "deletion-request"] as const,
};

export const dynamicUserAdminKeys = {
  all: ["dynamic_user_admin"] as const,
  users: (params?: AdminUsersParams) => [...dynamicUserAdminKeys.all, "users", params] as const,
  user: (id: number) => [...dynamicUserAdminKeys.all, "users", id] as const,
  userProfile: (id: number) => [...dynamicUserAdminKeys.all, "users", id, "profile"] as const,
  userSetting: (id: number) => [...dynamicUserAdminKeys.all, "users", id, "setting"] as const,
  deletionRequests: (params?: AdminDeletionRequestsParams) =>
    [...dynamicUserAdminKeys.all, "deletion-requests", params] as const,
  deletionRequest: (id: number) => [...dynamicUserAdminKeys.all, "deletion-requests", id] as const,
};
```

Five mutation hooks must never fire on mount, only from an explicit `mutate()` call
(`APP-DESIGN.md` §12's frontend security checklist): `useRequestDeletion`,
`useCancelDeletionRequest`, `useUpdateAdminUser`, `useReviewDeletionRequest`,
`useFinalizeDeletionRequest`.

**Requires another app package: No** (`appkit`'s `useApiClient`/`ApiClientProvider`/`HttpClient`
are the declared-dependency exception, per `APP-DESIGN.md` §1.1/§12).

---

## §8. `tasks.py` (celery extra only)

```python
# dynamic_user.tasks
@shared_task(name="dynamic_user.tasks.finalize_due_deletions")
def finalize_due_deletions() -> int:
    """Queries AccountDeletionRequest where status=APPROVED and finalize_at<=now(), calls
    DeletionService.finalize(row.id) per row. Continues past a single row's failure (logs it)
    rather than aborting the whole batch. Returns the count actually finalized."""
    ...


@shared_task(name="dynamic_user.tasks.purge_deletion_history")
def purge_deletion_history(older_than_days: int | None = None) -> int:
    """Deletes FINALIZED/REJECTED AccountDeletionRequest rows older than older_than_days
    (defaults to DYNAMIC_USER["DELETION_HISTORY_RETENTION_DAYS"]). Never touches PENDING/
    APPROVED rows regardless of age. Returns the count deleted."""
    ...
```

Recommended schedule: `finalize_due_deletions` — daily at 03:00; `purge_deletion_history` —
weekly. Behind the `celery` extra only; `management/commands/process_deletion_requests.py` calls
`finalize_due_deletions`'s underlying logic directly (same function, not a duplicate) for a host
running no Celery worker.

**Requires another app package: No.**

---

## §9. Dependencies

```toml
dependencies = [
    "django>=5.2,<7.0",
    "djangorestframework>=3.15,<4.0",
    "drf-spectacular>=0.27,<1.0",
    "hjtdev-appkit>=2.0,<3.0",
]

[project.optional-dependencies]
celery = ["celery[redis]>=5.4,<6.0", "django-celery-beat>=2.7,<3.0"]
avatar = ["hjtdev-appkit[images]>=2.0,<3.0"]
```

`django`, `djangorestframework`, `drf-spectacular` are the shared-platform ranges every app in
this ecosystem declares identically (`APP-DESIGN.md` §1.1) — a host almost certainly depends on
all three directly already. `hjtdev-appkit>=2.0,<3.0` is verified live against
`appkit/backend/pyproject.toml`'s actual `version = "2.0.2"`. **`avatar = ["hjtdev-appkit[images]
>=2.0,<3.0"]` is confirmed correct** — `appkit`'s own `[project.optional-dependencies]` names its
Pillow extra exactly `images`, not `avatar` or anything else; the guide's guess matches the real
source. No exact pins anywhere.

**Requires another app package: No.**

---

## §10. Deviations register

Everything not listed here is unchanged from
`docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`'s Phase 0 prompt.

1. **Throttle scopes are literal strings, not `appkit.throttling.throttle_scope()` calls.** Read
   from `appkit/backend/src/appkit/throttling.py`: the helper raises `ValueError` if either
   argument contains an underscore, and every scope this app needs (`dynamic_user_me`,
   `dynamic_user_admin_users_list`, …) has one in its own namespace segment. `appkit.checks`' W004
   system check still validates each literal against `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`
   regardless of how the string was produced — the same situation `cleanup_app`'s own
   `CONTRACT.md` §9.3 already recorded for the same helper.
2. **`PROFILE_PUBLIC_FIELDS` default narrowed to `["id", "bio"]`, plus a new `USER_PUBLIC_FIELDS`
   key (`["id", "username"]`) for the nested user block.** Confirmed with the user: narrowing this
   default later is a MAJOR bump per `CLAUDE.md`, so starting minimal and widening (a MINOR bump)
   is the strictly safer default for every host that never overrides it.
3. **`managers.py`'s `UserManager` added** — required by `AbstractBaseUser`, omitted from the
   Phase 0 prompt's item 1. `create_superuser` is the one place `is_staff`/`is_superuser` are
   written outside an HTTP request entirely, documented as an explicit, bounded, non-HTTP
   exception to the escalation rail (§0 item 3).
4. **`AvatarMixin` is not composed into `AbstractProfile`.** Confirmed with the user: an
   `ImageField` needs Pillow at `manage.py check` time regardless of whether one is ever uploaded,
   so baking it into the default `Profile` would make the `[avatar]` extra mandatory for every
   host, contradicting §0/§9. A host that wants avatars composes it itself.
5. **`services.py` return types refined to `AbstractProfile`/`AbstractSetting`** rather than the
   prompt's literal `-> Profile`/`-> Setting` — the concrete names would themselves be a forbidden
   concrete import; the abstract base is the accurate and import-safe type for any resolved model.
6. **`GET /profiles/{id}/`'s `{id}` is the target user's id**, not the `Profile` row's own primary
   key — matches how every other self-service route on this surface addresses "the current user,"
   and avoids a second id space a frontend would otherwise have to track per profile. Not stated
   explicitly in the Phase 0 prompt; made explicit here since Phase 5 implements against this file.
7. **Admin paths collapse to the basePath root**: `/api/v1/admin/users/42/`, not the prompt's
   literal `/users/{id}/` under an already-`/users`-suffixed basePath (which would read
   `/api/v1/admin/users/users/42/`). Confirmed with the user. `deletion-requests` stays a named
   segment so it can never collide with an integer user id.
8. **`CanEscalatePrivilege`'s gated field set extended to five fields** —
   `is_active`, `is_staff`, `is_superuser`, **`groups`, `user_permissions`** — beyond the guide's
   three-field (`is_staff`/`is_superuser`/`is_active`) list. `PermissionsMixin` gives every user
   `groups`/`user_permissions`; leaving them ungated on the admin `PATCH /{id}/` would let a
   non-superuser staff admin grant themselves (or anyone) superuser-equivalent capability through
   a permission/group assignment instead of the boolean flags the guard already covers — the same
   escalation the guard exists to prevent, reached by a side door.
9. **The three-way "unknown allowlist field" contradiction (Phase 0 prompt vs. Phase 4 prompt vs.
   `CLAUDE.md` rule 3) resolved as: fail loudly, but at startup, never mid-request** — a
   `checks.py` system check plus `build_serializer()`'s own `ImproperlyConfigured`, both naming
   the field and setting key. Confirmed with the user; full reasoning in §6.
10. **Two admin write hooks split from the guide's shared name** —
    `useUpdateAdminUserProfile(id)`/`useUpdateAdminUserSetting(id)` named distinctly from
    `useAdminUserProfile(id)`/`useAdminUserSetting(id)`, matching the read/write hook split every
    other resource in §7 already has. No hook from the guide's list is dropped.
11. **`services.py` gains two exception types** (`DeletionRequestAlreadyExists`,
    `InvalidDeletionState`) not named in the Phase 0 prompt, so §5's `409` responses are a
    documented mapping from a named exception rather than an ad hoc status code chosen at view
    level with nothing to import and assert against in tests.
12. **Seven `DYNAMIC_USER` keys added** beyond the prompt's explicit list — `USER_PUBLIC_FIELDS`,
    `USER_PRIVILEGED_FIELDS`, `PROFILE_READ_FIELDS`, `SETTING_READ_FIELDS`,
    `DELETION_ANONYMIZE_FUNCTION`, `DELETION_HISTORY_RETENTION_DAYS`,
    `LAST_SEEN_UPDATE_SECONDS` — each one required by a mechanism this contract specifies (the
    public-profile nested user block, the escalation-gate floor, read-only serializers separate
    from editable ones, the anonymize mode's actual callable, the purge task's default window, and
    `LastSeenMixin`'s write-throttling) that the prompt's own minimum list didn't yet name a
    setting for.
13. **Jazzmin is explicitly not a dependency** — stated in §0 because the Phase 0 prompt never
    raises it, and a reader coming from a project that *does* bundle `django-jazzmin` could
    otherwise assume it's declared here the way `appkit` is.
14. **`dynamic_user/migrations/0001_initial.py` carries `migrations.swappable_dependency
    (settings.AUTH_USER_MODEL)`, but deliberately carries no equivalent for this app's own
    `DYNAMIC_USER_PROFILE_MODEL`/`DYNAMIC_USER_SETTING_MODEL` settings** — a refinement of the
    Phase 2 prompt's literal instruction ("add `migrations.swappable_dependency` for those two
    settings as well"), reached by reading the installed Django 6.0.8 migration-loader/
    autodetector source rather than assuming the instruction was safe as written, and confirmed
    by generating and inspecting the real migrations for three separate host layouts.

    **What's kept, and why it's needed.** `Profile`/`Setting`/`AccountDeletionRequest`/
    `ChangeLogEntry` all FK/O2O to `settings.AUTH_USER_MODEL`. Django's own `makemigrations`
    autodetector did *not* add this dependency when first generating this file — because, under
    the settings module it ran against, `AUTH_USER_MODEL` resolved to this same migration's own
    `User`, which `add_internal_dependencies` (`django/db/migrations/loader.py`) correctly
    treats as needing no edge for *that* run. But this file ships fixed, for every host: one that
    swaps `AUTH_USER_MODEL` to a different app entirely, while leaving `Profile`/`Setting` at
    this app's own defaults, needs that other app's `User` table to exist before this migration
    creates rows referencing it — exactly the precedent `django.contrib.admin`'s own `LogEntry`
    migration sets (verified against the installed source: `admin/migrations/0001_initial.py`
    carries `swappable_dependency(settings.AUTH_USER_MODEL)` for the same reason, since
    `LogEntry.user` FKs to it from a different app than the one defining `User`). The dependency
    was added back into this file by hand after generation. Proven safe for the common case too:
    when `AUTH_USER_MODEL` still resolves to this app's own `User` (the default), the loader's
    `check_key()` drops a same-app `__first__` reference as a no-op (ticket #22325) — it only
    becomes a real graph edge when the target genuinely lives elsewhere. Exercised for real by
    `tests/backend/settings_user_swap.py`/`test_user_swap.py` (`AUTH_USER_MODEL` swapped,
    `Profile`/`Setting` at their defaults) alongside the unswapped leg
    (`tests/backend/settings.py`), which together prove both directions of this one dependency.

    **What's omitted, and why it would break.** Nothing in `dynamic_user`'s own migration file
    references "the resolved profile/setting model" via FK/O2O — `Profile`/`Setting` themselves
    *are* those models; `options={'swappable': ...}` on their own `CreateModel` operations
    (present since generation, untouched) is the complete, correct mechanism Django already uses
    to skip creating their table when a host swaps them out. Adding a
    `swappable_dependency(DYNAMIC_USER_PROFILE_MODEL)`/`(DYNAMIC_USER_SETTING_MODEL)` edge as
    well — the Phase 2 prompt's literal instruction — creates a two-node
    `CircularDependencyError` for the single most plausible partial-swap host: one that swaps
    only `Profile`/`Setting` to its own app while leaving `AUTH_USER_MODEL` at this app's
    default. That host's own app needs `swappable_dependency(AUTH_USER_MODEL)` to point back at
    `dynamic_user` (a real edge, since `AUTH_USER_MODEL` is external from *that* app's
    perspective); `dynamic_user`'s migration depending back on that host app for
    `DYNAMIC_USER_PROFILE_MODEL` would close the cycle. Verified live: generating and inspecting
    `tests/backend/partial_app/migrations/0001_initial.py` shows exactly the real
    `swappable_dependency(settings.AUTH_USER_MODEL)` edge described above, and
    `dynamic_user/migrations/0001_initial.py` carries no dependency back on `partial_app` —
    `tests/backend/test_partial_swap.py` applies this exact layout against real Postgres from
    zero as the concrete, executable proof.
15. **`ChangeLogEntry` is defined in `models.py`, not inside the `mixins.py` code block §1 shows
    it in.** Django only auto-imports an app's `models.py` when building the app registry; a
    concrete model defined in `mixins.py` would never be discovered/migrated unless something
    else happened to import that module first. `HistoryMixin.log_change()` (`mixins.py`) reaches
    it through a function-local import (`from dynamic_user.models import ChangeLogEntry`) — a
    placement change only; no field, name, or index differs from what §1 specifies.

---

## §11. Semver triggers (concrete, against the names frozen above)

Per `CLAUDE.md`'s own list, restated against this file's exact names:

- Removing/renaming any of the six §3 signals, or narrowing/renaming a payload kwarg.
- Removing/renaming a `services.py` method, changing its signature, or removing
  `DeletionRequestAlreadyExists`/`InvalidDeletionState`.
- Renaming any `DYNAMIC_USER` key in §6, or `DYNAMIC_USER_PROFILE_MODEL`/
  `DYNAMIC_USER_SETTING_MODEL`.
- Narrowing `USER_READ_FIELDS`, `USER_EDITABLE_FIELDS`, `USER_PUBLIC_FIELDS`,
  `PROFILE_READ_FIELDS`, `PROFILE_EDITABLE_FIELDS`, `PROFILE_PUBLIC_FIELDS`,
  `SETTING_READ_FIELDS`, or `SETTING_EDITABLE_FIELDS`'s default. **Shrinking**
  `USER_PRIVILEGED_FIELDS`' floor below the five fields in §6 is a breaking change even though
  it's "just a default," per `CLAUDE.md`'s own rule — a host that never overrode it silently loses
  a safety rail.
- Changing `build_serializer()`'s signature, or what `resolution.py` returns/raises.
- Changing `ADMIN_REQUIRES_SUPERUSER`'s default, `DELETION_GRACE_PERIOD_DAYS`'s default,
  `DELETION_MODE`'s default, or loosening `CanEscalatePrivilege`'s five-field gate.
- Renaming `django-dynamic-user` / `@hjtdev/django-dynamic-user`.

Every one of these needs a **Host action:** line in `CHANGELOG.md`, per `CLAUDE.md`.

### Open items — deliberately not resolved in Phase 0

- **`DELETION_REQUIRES_REVIEW`** — should a host be able to configure deletion to skip admin
  review entirely (auto-approve on request)? Not added here; the current shape always requires an
  explicit `DeletionService.review()` call. Revisit if a real host asks for it.
- **`PUBLIC_PROFILES_ENABLED`** — should the whole `/profiles/`, `/profiles/{id}/` surface be
  switchable off for a host that never wants a public directory? Not added here; `is_public`
  already lets every individual user opt out, which may be sufficient.

---

Per §0–§8: **Requires another app package: No** for every one, `django.contrib.contenttypes`
named as the single sanctioned exception (`HistoryMixin`/`ChangeLogEntry`, §1), exactly as
`APP-DESIGN.md` §6 and this guide's own three rails require.
