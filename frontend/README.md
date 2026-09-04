# django-dynamic-user

Swappable `User`/`Profile`/`Setting` data layer for a host Django project, as an installable app
package.

- **Importable module:** `dynamic_user`.
- **PyPI distribution:** `django-dynamic-user`. **npm package:** `@hjtdev/django-dynamic-user`.
- This app does not do authentication — no registration, login, JWT, or password reset. It is the
  data layer a separate `auth-app` package reaches through `get_user_model()`, the same
  indirection `django.contrib.auth`'s own views use.
- Requires another app package: **No.** `hjtdev-appkit` is a real, versioned dependency (cache,
  pagination, permissions, error envelope, `HttpClient`/provider) — install and wire it *before*
  this app; the settings block below assumes `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` already
  exists as a dict, and that appkit's `standard_exception_handler` is already the configured
  `EXCEPTION_HANDLER`.

## Installation — backend

```bash
uv add "django-dynamic-user>=1.0,<2.0"
```

Pinning an unreleased commit instead of a tagged release works too, via the git+subdirectory form:

```bash
uv add "git+https://github.com/HjtDev/django-dynamic-user.git@v1.0.0#subdirectory=backend"
```

Optional extras:

```bash
uv add "django-dynamic-user[celery]"   # celery[redis] + django-celery-beat, for scheduled tasks
uv add "django-dynamic-user[avatar]"   # Pillow via hjtdev-appkit[images], for AvatarMixin
```

Neither extra is required for the app to be fully functional — see "Recommended periodic
schedule" and the `AvatarMixin` row of the mixins table below.

## Compatibility

- Python 3.13+ · Django 5.2–6.x · Django REST Framework 3.15+ · drf-spectacular 0.27+
- `hjtdev-appkit>=2.0,<3.0` — a declared dependency, not optional.
- Requires `django.contrib.contenttypes` (present by default with the admin) — the one place this
  app touches it is `ChangeLogEntry`, the concrete model behind `HistoryMixin.log_change()`.

## The two swappable-model settings

This app ships three swappable models, resolved the same way `django.contrib.auth.get_user_model()`
resolves `AUTH_USER_MODEL`:

| Setting | Django mechanism | Default if unset |
|---|---|---|
| `AUTH_USER_MODEL` | Django's own top-level setting | Not this app's to default — a host must always set this itself once any custom user model is involved |
| `DYNAMIC_USER_PROFILE_MODEL` | top-level, `"app_label.ModelName"` | `"dynamic_user.Profile"` |
| `DYNAMIC_USER_SETTING_MODEL` | top-level, `"app_label.ModelName"` | `"dynamic_user.Setting"` |

All three exist **because Django's `swappable_dependency()` machinery expects a top-level setting
name**, not a `DYNAMIC_USER` dict key — the same reason `AUTH_USER_MODEL` itself isn't nested
inside anything. `dynamic_user.User`/`Profile`/`Setting` are usable as-is (a host that wants zero
customization sets all three settings to `dynamic_user.User`/`.Profile`/`.Setting`, or omits the
two `DYNAMIC_USER_*` ones and lets them default), **or** a host subclasses any of the three
abstract bases to add project-specific fields with zero changes to this package's own code.

**`AUTH_USER_MODEL` is a pre-first-migrate decision, not a runtime setting.** Django resolves
`USERNAME_FIELD`/`REQUIRED_FIELDS` at class-definition time, and changing which concrete model
`AUTH_USER_MODEL` points at after the first `migrate` is the same unsupported operation it always
is in Django — decide before you run `migrate` for the first time, not after.

### Worked subclassing example

Every extra field below round-trips over real HTTP in this package's own two-host playground
(`playground/subclassed/`) with zero package-level code changes — only the `DYNAMIC_USER` dict's
allowlists need to name the new field.

```python
# core/models.py
from django.db import models

from dynamic_user.managers import UserManager
from dynamic_user.models import AbstractDynamicUser, AbstractProfile, AbstractSetting


class User(AbstractDynamicUser):
    department = models.CharField(max_length=100, blank=True)

    # Required — AbstractDynamicUser doesn't declare `objects` as inheritable in a way Django's
    # migration state picks up automatically; every host subclass must re-declare it. Easy to
    # omit; `createsuperuser`/`create_user` breaks with a cryptic error without it.
    objects = UserManager()


class Profile(AbstractProfile):
    tagline = models.CharField(max_length=200, blank=True)


class Setting(AbstractSetting):
    theme = models.CharField(max_length=20, default="light")
```

None of these three declare `Meta.swappable` themselves — that attribute belongs to
`dynamic_user`'s own default implementation, marking "this is the model a setting can swap away
from." A host's replacement model is simply whatever `AUTH_USER_MODEL`/
`DYNAMIC_USER_PROFILE_MODEL`/`DYNAMIC_USER_SETTING_MODEL` names — it needs no `swappable`
attribute of its own, exactly like any other project's custom `AUTH_USER_MODEL`.

```python
# config/settings.py
INSTALLED_APPS += ["core"]  # must be installed BEFORE "dynamic_user" is added, or Django's
                             # swappable-model resolution can't find it at migration time

AUTH_USER_MODEL = "core.User"
DYNAMIC_USER_PROFILE_MODEL = "core.Profile"
DYNAMIC_USER_SETTING_MODEL = "core.Setting"

DYNAMIC_USER = {
    "USER_READ_FIELDS": ["id", "username", "name", "email", "phone", "is_active",
                          "date_joined", "department"],
    "PROFILE_EDITABLE_FIELDS": ["bio", "is_public", "tagline"],
    "SETTING_EDITABLE_FIELDS": ["language", "timezone", "notifications_enabled", "theme"],
}
```

A name in any `*_FIELDS` allowlist that doesn't exist on the *resolved* model is caught at
**startup**, not mid-request — see "System checks" below.

## Settings — add to `backend/config/settings.py`

Copy this block verbatim. It is lifted directly from this package's own default-host playground
(`playground/default/backend/config/settings.py`), which boots on it unmodified — the same block
CI's `readme-contract` job (from v1.0.0 onward) will diff the code's real throttle scopes against.

```python
# ============================================================================================
# DYNAMIC_USER WIRING
# ============================================================================================

INSTALLED_APPS += ["dynamic_user"]

MIDDLEWARE += []  # none required

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "dynamic_user_me": "60/min",
    "dynamic_user_profile_update": "20/min",
    "dynamic_user_setting_update": "20/min",
    "dynamic_user_profiles_list": "60/min",
    "dynamic_user_profile_retrieve": "60/min",
    "dynamic_user_deletion_request": "10/min",
    "dynamic_user_admin_users_list": "60/min",
    "dynamic_user_admin_user_retrieve": "60/min",
    "dynamic_user_admin_user_update": "30/min",
    "dynamic_user_admin_profile_update": "30/min",
    "dynamic_user_admin_setting_update": "30/min",
    "dynamic_user_admin_deletions_list": "60/min",
    "dynamic_user_admin_deletion_review": "20/min",
    "dynamic_user_admin_deletion_finalize": "10/min",
})

# The package's own concrete models, used as-is. Every DYNAMIC_USER key below is optional with a
# documented default (see the table further down) — omit the whole dict for zero customization.
AUTH_USER_MODEL = "dynamic_user.User"
DYNAMIC_USER_PROFILE_MODEL = "dynamic_user.Profile"
DYNAMIC_USER_SETTING_MODEL = "dynamic_user.Setting"

# ============================================================================================
# END DYNAMIC_USER WIRING
# ============================================================================================
```

Rates shown above are this package's own playground defaults, not a hard requirement — tune them
per host, just keep every scope name exact (they're literal strings, not derived from a helper).

### `DYNAMIC_USER` settings — every key, with its default

All 20 keys are optional at the Python level; a host overrides only what it needs to change.

| Key | Default | Meaning |
|---|---|---|
| `USER_READ_FIELDS` | `["id", "username", "name", "email", "phone", "is_active", "date_joined"]` | Fields on `GET /me/` and the admin user read views (admin sees the full model regardless, except `password`) |
| `USER_EDITABLE_FIELDS` | `["name", "phone"]` | Not currently consumed by any shipped route — `GET /me/` is read-only and admin `PATCH` writes the full model. Kept for forward-compat with a future self-service `/me/` `PATCH`; validated by `dynamic_user.E005` regardless |
| `USER_LOCKED_FIELDS` | `["username", "email", "is_staff", "is_superuser", "is_active"]` | Subtracted from `USER_EDITABLE_FIELDS` at build time even if a host also lists one of these there — belt-and-braces, deterministic |
| `USER_PUBLIC_FIELDS` | `["id", "username"]` | Fields on the nested `user` block of a public profile response |
| `USER_PRIVILEGED_FIELDS` | `["is_staff", "is_superuser", "is_active", "groups", "user_permissions"]` | The exact key set `CanEscalatePrivilege` gates on admin `PATCH /{id}/`. A host may only **add** to this set — the resolved value is always `DEFAULT ∪ host's`, never smaller |
| `PROFILE_READ_FIELDS` | `["id", "bio", "is_public"]` | Fields on `GET /me/profile/` |
| `PROFILE_EDITABLE_FIELDS` | `["bio", "is_public"]` | Fields on `PATCH /me/profile/` |
| `PROFILE_PUBLIC_FIELDS` | `["id", "bio"]` | Fields on `/profiles/`, `/profiles/{id}/` — deliberately minimal |
| `SETTING_READ_FIELDS` | `["id", "language", "timezone", "notifications_enabled"]` | Fields on `GET /me/setting/` |
| `SETTING_EDITABLE_FIELDS` | `["language", "timezone", "notifications_enabled"]` | Fields on `PATCH /me/setting/` |
| `PHONE_VALIDATORS` | `[]` | Dotted callable paths, resolved lazily and cached on first use. Empty = no extra validation beyond Django's own field checks — **no opinionated phone format ships by default** |
| `NAME_VALIDATORS` | `[]` | Same shape, for `name` |
| `ADMIN_REQUIRES_SUPERUSER` | `False` | `True` tightens every admin gate from `is_staff` to `is_superuser`. Never loosens `CanEscalatePrivilege` or the deletion-finalize gate, either way |
| `AUTO_CREATE_PROFILE` | `True` | Connects a `post_save(created=True)` receiver on the user model that `get_or_create`s a Profile row and sends `profile_created` |
| `AUTO_CREATE_SETTING` | `True` | Same, for Setting/`setting_created` |
| `DELETION_MODE` | `"hard_delete"` | `"hard_delete"` or `"anonymize"` |
| `DELETION_GRACE_PERIOD_DAYS` | `14` | `finalize_at = requested_at + this many days`, computed at request time |
| `DELETION_ANONYMIZE_FUNCTION` | `None` | Dotted path to a callable `(user) -> None`, called by `.finalize()` when `DELETION_MODE="anonymize"`. Required in that mode — fails closed (`ImproperlyConfigured`) rather than silently falling back to hard-delete |
| `DELETION_HISTORY_RETENTION_DAYS` | `90` | Default window `tasks.purge_deletion_history` uses when not passed an explicit `older_than_days` |
| `LAST_SEEN_UPDATE_SECONDS` | `300` | Minimum interval `LastSeenMixin`'s update path (a host-wired hook, not a view this package ships) writes a new `last_seen_at` |

A settings change never produces a migration diff — every one of these is resolved at call time,
never baked into a model's class attributes. The one exception, forced by Django itself, is
`USERNAME_FIELD`/`REQUIRED_FIELDS` on the user model's abstract base (see above).

### System checks

Run automatically on `manage.py check` (and therefore `migrate`/`runserver`) — a misconfiguration
is a named startup error, never a mid-request crash and never a silent drop:

| Code | Catches |
|---|---|
| `dynamic_user.E001` | `DYNAMIC_USER_PROFILE_MODEL`/`DYNAMIC_USER_SETTING_MODEL` not shaped `"app_label.ModelName"` |
| `dynamic_user.E002` | One of those settings names a model that isn't installed |
| `dynamic_user.E003` | `DELETION_MODE` is neither `"hard_delete"` nor `"anonymize"`, or it's `"anonymize"` with no `DELETION_ANONYMIZE_FUNCTION` set |
| `dynamic_user.E005` | A name in any `*_FIELDS` allowlist (including `USER_PRIVILEGED_FIELDS`) that doesn't exist on the resolved model |

## Required `.env` keys

**None.** Zero `.env` keys, required or optional, under any installed extra. This app configures
entirely through the `DYNAMIC_USER` dict plus the two top-level swappable-model settings above.

## URL mounting — add to `backend/config/urls.py`

Two separate URLconfs, two separate namespaces — self-service and admin are never mounted
together under one path:

```python
urlpatterns = [
    ...
    path("api/v1/users/", include("dynamic_user.urls")),
    path("api/v1/admin/users/", include("dynamic_user.urls_admin")),
]
```

Admin paths collapse to the basePath root — `/api/v1/admin/users/42/`, not
`/api/v1/admin/users/users/42/`.

## Migrations

```bash
uv run python manage.py migrate dynamic_user
```

If you subclassed any of the three models, run your own app's `makemigrations`/`migrate` for that
app instead — `dynamic_user`'s own migrations only apply when its concrete `User`/`Profile`/
`Setting` are actually in use. `ChangeLogEntry` (the model behind `HistoryMixin`) is not
swappable and always migrates with `dynamic_user` regardless.

## Endpoints

### Self-service — `dynamic_user.urls`, basePath `/api/v1/users`

Every object here is resolved from `request.user`, never a URL-supplied id, except
`GET /profiles/{id}/` — the one place this surface looks up someone else's (public) data.

| Method | Path | Permission | Throttle scope |
|---|---|---|---|
| `GET` | `/me/` | `IsAuthenticated` | `dynamic_user_me` |
| `GET` | `/me/profile/` | `IsAuthenticated` | `dynamic_user_me` |
| `PATCH` | `/me/profile/` | `IsAuthenticated`, `IsProfileOwner` | `dynamic_user_profile_update` |
| `GET` | `/me/setting/` | `IsAuthenticated` | `dynamic_user_me` |
| `PATCH` | `/me/setting/` | `IsAuthenticated`, `IsProfileOwner` | `dynamic_user_setting_update` |
| `GET` | `/profiles/` | `IsAuthenticated` | `dynamic_user_profiles_list` |
| `GET` | `/profiles/{id}/` | `IsAuthenticated`, `IsPublicOrOwner` | `dynamic_user_profile_retrieve` |
| `POST` `GET` `DELETE` | `/me/deletion-request/` | `IsAuthenticated` | `dynamic_user_deletion_request` |

`GET /profiles/{id}/`'s `{id}` is the target **user's** id, not the Profile row's own primary key.
A private profile 404s (not 403) for a non-owner. `POST /me/deletion-request/` 409s if a
pending/approved request already exists; `DELETE` 409s if the caller's current request isn't
`PENDING`.

### Admin — `dynamic_user.urls_admin`, basePath `/api/v1/admin/users`

Every view is gated by `IsDynamicUserAdmin` (`is_staff`, or `is_superuser` when
`ADMIN_REQUIRES_SUPERUSER=True`) at minimum.

| Method | Path | Extra gate | Throttle scope |
|---|---|---|---|
| `GET` | `/` | — | `dynamic_user_admin_users_list` |
| `GET` | `/{id}/` | — | `dynamic_user_admin_user_retrieve` |
| `PATCH` | `/{id}/` | `CanEscalatePrivilege` | `dynamic_user_admin_user_update` |
| `GET` `PATCH` | `/{id}/profile/` | — | `dynamic_user_admin_profile_update` |
| `GET` `PATCH` | `/{id}/setting/` | — | `dynamic_user_admin_setting_update` |
| `GET` | `/deletion-requests/` | — | `dynamic_user_admin_deletions_list` |
| `POST` | `/deletion-requests/{id}/review/` | — | `dynamic_user_admin_deletion_review` |
| `POST` | `/deletion-requests/{id}/finalize/` | **superuser-only, always** | `dynamic_user_admin_deletion_finalize` |

**The privilege-escalation gate.** `CanEscalatePrivilege` runs only on admin `PATCH /{id}/`, is
never controlled by `ADMIN_REQUIRES_SUPERUSER`, and inspects the request body for the exact key
set `{"is_active", "is_staff", "is_superuser", "groups", "user_permissions"}` (the
`USER_PRIVILEGED_FIELDS` floor above, plus any host additions). If the body touches **any** of
those keys and `request.user.is_superuser` is not `True`, the entire request is rejected with
`403` — never a silent per-field drop. `password` is excluded from every serializer this app
produces or accepts, unconditionally. `POST /deletion-requests/{id}/finalize/` is superuser-only
**regardless** of `ADMIN_REQUIRES_SUPERUSER` — it bypasses the grace period entirely and is
genuinely irreversible.

## Signals emitted

Every payload is a bare id or primitive, never a model instance. `sender` for
`profile_created`/`setting_created`/`profile_updated` is the *resolved* class — filter with
`@receiver(profile_created, sender=get_profile_model())`, works correctly even under a swapped
model.

| Signal | Sender | Payload |
|---|---|---|
| `profile_created` | resolved Profile model | `user_id: int` |
| `setting_created` | resolved Setting model | `user_id: int` |
| `deletion_requested` | `AccountDeletionRequest` | `user_id: int`, `request_id: int`, `finalize_at: datetime` |
| `deletion_reviewed` | `AccountDeletionRequest` | `request_id: int`, `status: str`, `reviewed_by_id: int \| None` |
| `deletion_finalized` | `AccountDeletionRequest` | `user_id: int` (captured before a `hard_delete` removes the row), `mode: str` |
| `profile_updated` | resolved Profile model | `user_id: int`, `changed_fields: list[str]` — sent only when at least one field actually changed |

`profile_created`/`setting_created` only fire when `AUTO_CREATE_PROFILE`/`AUTO_CREATE_SETTING`
(both default `True`) are enabled and a row was actually created — not on every `get_or_create`.
Setting changes emit no signal (not yet part of the versioned-contract surface).

Payload changes to any of the above are a **MAJOR** version bump.

## Services (public callables) — `dynamic_user.services`

The only place a Profile/Setting update or an account-deletion state transition happens. Every
model reference is resolved through `resolution.py`/`settings.AUTH_USER_MODEL` at call time.

| Method | Signature | Notes |
|---|---|---|
| `ProfileService.update` | `(user: AbstractBaseUser, validated_data: dict) -> AbstractProfile` | `get_or_create`s the row; sends `profile_updated` if anything changed |
| `SettingService.update` | `(user: AbstractBaseUser, validated_data: dict) -> AbstractSetting` | Same shape; no signal |
| `DeletionService.current` | `(user: AbstractBaseUser) -> AccountDeletionRequest \| None` | The user's active (`PENDING`/`APPROVED`) request, or `None` |
| `DeletionService.request` | `(user: AbstractBaseUser, *, reason: str = "") -> AccountDeletionRequest` | Raises `DeletionRequestAlreadyExists` if one is already active |
| `DeletionService.review` | `(request_id: int, *, approved: bool, reviewed_by: AbstractBaseUser) -> AccountDeletionRequest` | Raises `InvalidDeletionState` unless currently `PENDING`. Rejecting is terminal |
| `DeletionService.finalize` | `(request_id: int) -> None` | Raises `InvalidDeletionState` unless currently `APPROVED`. Implements `DELETION_MODE`; raises `ImproperlyConfigured` on a misconfigured `"anonymize"` mode rather than falling back |
| `DeletionService.cancel` | `(user: AbstractBaseUser) -> None` | Raises `InvalidDeletionState` if no `PENDING` request exists. Deletes the row outright — no "cancelled" status |

Signature changes to any of the above are a **MAJOR** version bump.

## Mixins — `dynamic_user.mixins`

One composable abstract model per mixin. Compose onto your own subclass of `AbstractDynamicUser`/
`AbstractProfile`/`AbstractSetting` as needed — none are applied by default.

| Mixin | Fields added | Composing-model requirement |
|---|---|---|
| `AvatarMixin` | `avatar`, `avatar_updated_at` | Needs the `[avatar]` extra only if actually used — the import itself never requires Pillow |
| `TimestampMixin` | `created_at`, `updated_at` | None |
| `HistoryMixin` | none (adds `.log_change(field, old, new, *, actor=None)`) | None — writes to the always-migrated, non-swappable `ChangeLogEntry` |
| `SoftDeleteMixin` | `is_deleted`, `deleted_at` | The composing model must define its own `objects` (filtered) and `all_objects` (unfiltered) managers — a mixin can't safely inject a manager onto `User`, which already needs `UserManager` |
| `VerificationMixin` | `email_verified`, `email_verified_at`, `phone_verified`, `phone_verified_at` | None — flags and timestamps only, no delivery logic |
| `LastSeenMixin` | `last_seen_at`, `last_seen_ip` | None — write-throttling per `LAST_SEEN_UPDATE_SECONDS` is a host-wired hook's job |
| `MetadataMixin` | `metadata` (`JSONField`) | None — never read/written by this package's own views/serializers by default |

## Test helpers

`dynamic_user.factories` exports `factory_boy` factories for `User`/`Profile`/`Setting`/
`AccountDeletionRequest` — this package's public test-only surface. Add `factory-boy` to your own
test dependency group to use them; this module is never imported by anything under this package's
own `src/`.

## Recommended periodic schedule

Behind the `celery` extra only — this app is fully functional with no worker running at all. A
host without Celery drives the exact same underlying logic via
`python manage.py process_deletion_requests` (`finalize_due_deletions` only) on plain cron
instead; there is no cron-only equivalent of `purge_deletion_history` shipped, add your own if you
want that one scheduled without Celery.

```
dynamic_user.tasks.finalize_due_deletions  — daily at 03:00
dynamic_user.tasks.purge_deletion_history  — weekly
```

This is a recommendation, not something that auto-registers — the host creates the actual
`django_celery_beat` schedule entry.

## Suggested Jazzmin icons

Jazzmin is not a dependency of this package — it never writes to `JAZZMIN_SETTINGS` itself. If a
host has Jazzmin installed:

```python
JAZZMIN_SETTINGS = {
    ...
    "icons": {
        "dynamic_user.user": "fas fa-user",
        "dynamic_user.profile": "fas fa-id-card",
        "dynamic_user.setting": "fas fa-sliders-h",
        "dynamic_user.accountdeletionrequest": "fas fa-user-slash",
        "dynamic_user.changelogentry": "fas fa-history",
    },
}
```

Re-key these to your own app label if you subclassed the swappable models (e.g.
`"core.user"` instead of `"dynamic_user.user"`) — `accountdeletionrequest` and
`changelogentry` stay `dynamic_user.*` either way, since neither is swappable.

## Installation — frontend

```bash
npm install @hjtdev/appkit                 # if not already installed
npm install @hjtdev/django-dynamic-user
```

Peer dependencies: `react>=18`, `@tanstack/react-query>=5`, `@hjtdev/appkit>=2.0.0 <3.0.0`.

## Usage — two `basePaths` entries, then import hooks from the package root

**This app registers two API surfaces, not one** — `dynamic_user` (self-service) and
`dynamic_user_admin` (admin). A host wiring only `dynamic_user` will see every admin hook 404 or
hit the self-service prefix instead; both entries are required on `@hjtdev/appkit`'s
`ApiClientProvider`, the one provider a host mounts for its whole app:

```tsx
// app/providers.tsx — one-time wiring per host
import { useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ApiClientProvider } from "@hjtdev/appkit";
import { makeQueryClient } from "@/lib/query-client";
import { apiClient } from "@/lib/api-client";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider
        client={apiClient}
        basePaths={{
          // ...entries for already-installed apps stay here
          dynamic_user: "/api/v1/users",
          dynamic_user_admin: "/api/v1/admin/users",
        }}
      >
        {children}
      </ApiClientProvider>
    </QueryClientProvider>
  );
}
```

Requires the host's `@tanstack/react-query` `QueryClientProvider` already mounted above these
hooks. No further frontend configuration needed.

### Self-service hooks

```tsx
import {
  useMe, useMyProfile, useUpdateMyProfile, useMySetting, useUpdateMySetting,
  usePublicProfiles, usePublicProfile,
  useMyDeletionRequest, useRequestDeletion, useCancelDeletionRequest,
  dynamicUserKeys,
} from "@hjtdev/django-dynamic-user";
```

### Admin hooks

```tsx
import {
  useAdminUsers, useAdminUser, useUpdateAdminUser,
  useAdminUserProfile, useUpdateAdminUserProfile,
  useAdminUserSetting, useUpdateAdminUserSetting,
  useAdminDeletionRequests, useReviewDeletionRequest, useFinalizeDeletionRequest,
  dynamicUserAdminKeys,
} from "@hjtdev/django-dynamic-user";

function AdminUserRow({ id }: { id: number }) {
  const { data: user } = useAdminUser(id);
  const { mutate: update } = useUpdateAdminUser(id);
  // ...
}
```

All 20 hooks and both key factories (`dynamicUserKeys`, `dynamicUserAdminKeys`) are exported from
the package root — there is no other entrypoint, and no provider export (the host mounts appkit's
`ApiClientProvider` once, as shown above).

---

## Where this README and `docs/CONTRACT.md` disagree

Code is the source of truth throughout this document. Phase 9 found four such spots; Phase 10
resolved three of them (`USER_EDITABLE_FIELDS`'s false "admin baseline" claim was corrected in
`docs/CONTRACT.md` §6 and `dynamic_user/conf.py`'s own comment, CI now exists, and the version
below is current). One remains, kept here as an accurate record rather than a discrepancy to fix:

1. **`ChangeLogEntry` is defined in `models.py`, not `mixins.py`.** `CONTRACT.md` §1 shows it
   inside the mixins code block. This is already recorded in `CONTRACT.md` §10 item 15 as a
   deliberate deviation (Django only auto-discovers models from `models.py`) — flagged here only
   to confirm the register entry is accurate, not to re-litigate it.

No other disagreements were found across the `DYNAMIC_USER` key table (all 20 keys, verified
against `conf.py DEFAULTS`), the six signal payloads, the seven service signatures, every
self-service/admin endpoint and its permission classes, all 20 frontend hook names, or the two
task names/recommended schedule.
