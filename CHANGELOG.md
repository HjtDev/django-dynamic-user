# Changelog

All notable changes to `django-dynamic-user` (backend) / `@hjtdev/django-dynamic-user` (frontend)
are documented here, [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. Both halves
release under one tag (`CLAUDE.md`'s "both halves release under one tag" rule) — there is one
changelog, not two.

Pre-`1.0.0`: entries accumulate under `[Unreleased]` as they land. Phase 10 collapses everything
built across Phases 0–9 into the real `[1.0.0]` entry when the first tag is cut, per
`docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`'s own Phase 10 — this section is the running list
that entry gets built from, not a substitute for it.

## [Unreleased]

## [1.0.1] - 2026-09-05

Phase 11 (`docs/PHASE-11-FINDINGS.md`): installed v1.0.0 into two fresh `base-scaffold` clones
(one default models, one fully subclassed), following `INTEGRATION-GUIDE.md` §2 using only
`README.md`. Documentation-only release — no backend or frontend source changed, no behavior
changed, no `Host action` required.

### Fixed

- **README — subclassing example**: added the missing `INSTALLED_APPS += ["dynamic_user"]` line.
  Following the example as previously written crashed at startup
  (`RuntimeError: Model class dynamic_user.models.User doesn't declare an explicit app_label...`)
  because `core/models.py`'s required import of the abstract bases also imports this package's
  own unconditionally-defined concrete `User`/`Profile`/`Setting` classes, which still need their
  app installed to resolve an `app_label` even when unused.
- **README — settings block**: documented that the "copy this block verbatim" block must be
  placed *after* `REST_FRAMEWORK` is defined in `settings.py` (it does
  `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update(...)`) — pasting it at the file's only marked
  insertion point (inside/after `INSTALLED_APPS`/`MIDDLEWARE`) raised `NameError`. Also noted the
  block needs `REST_FRAMEWORK: dict[str, Any]` to satisfy mypy, and a `ruff format` pass to
  satisfy the formatter, as pasted.
- **README — URL mounting**: the `urls.py` snippet was missing `from django.urls import include`.
- **README — subclassing example**: `objects = UserManager()` now shown as
  `objects: ClassVar[UserManager] = UserManager()` — the bare form fails mypy under django-stubs
  ("Cannot override class variable ... with instance variable").
- **README — basePaths warning corrected, not just softened**: the documented failure mode ("a
  host wiring only `dynamic_user` will see every admin hook 404") does not occur for a host that
  mounted the backend at this README's own recommended paths — confirmed live, twice, against the
  real shipped SDK: `appkit`'s `useApiClient` fallback default equals the correct URL, so omitting
  the `dynamic_user_admin` `basePaths` key produces byte-identical results to registering it. The
  README now describes the real risk (a *future* backend remount silently falling back) instead
  of a failure that doesn't reproduce under its own instructions.
- **README — frontend usage example**: `makeQueryClient` was shown imported from a
  `@/lib/query-client` module that doesn't exist in `base-scaffold`; corrected to import from
  `@hjtdev/appkit`, matching a real host's own `app/providers.tsx`.
- **README — system checks table**: added the missing `dynamic_user.E004` row (resolved model
  doesn't subclass this app's abstract base).
- **README**: added a "Verifying the install" section (none existed); noted that the weekly
  `purge_deletion_history` schedule needs a host-chosen day/hour, and clarified the "two
  swappable-model settings" heading against the three-row table beneath it.

## [1.0.0] - 2026-09-05

First tagged release. Everything below shipped across Phases 0–9; there is no prior release to
diff against, so this entry is organized by subsystem rather than by phase.

### Added

- **Data layer** (`models.py`, `mixins.py`, `migrations/0001_initial.py`): abstract
  `AbstractDynamicUser`/`AbstractProfile`/`AbstractSetting` bases plus swappable concrete
  `User`/`Profile`/`Setting` defaults, resolved everywhere via `settings.AUTH_USER_MODEL` /
  `resolution.get_profile_model()` / `resolution.get_setting_model()` — never a concrete import.
  `AccountDeletionRequest` and `ChangeLogEntry` models. `UserManager` (rejects an explicit
  `is_staff=False` on `create_superuser`). Seven composable mixins: `AvatarMixin`,
  `TimestampMixin`, `HistoryMixin` (`log_change()`, via `django.contrib.contenttypes`),
  `SoftDeleteMixin`, `VerificationMixin`, `LastSeenMixin`, `MetadataMixin`. `run_validators()` plus
  the `PHONE_VALIDATORS`/`NAME_VALIDATORS` region-specific hook points.
- **Business logic** (`services.py`, `signals.py`, `tasks.py`): `ProfileService.update()`,
  `SettingService.update()`, and `DeletionService` (`current()`, `request()`, `review()`,
  `finalize()`, `cancel()`) implementing the full opt-out account-deletion state machine.
  Auto-provisioning receivers (`connect_profile_auto_provisioning()`,
  `connect_setting_auto_provisioning()`) wired through `apps.py.ready()` against the *resolved*
  models, gated by `AUTO_CREATE_PROFILE`/`AUTO_CREATE_SETTING`. Six signals: `profile_created`,
  `setting_created`, `deletion_requested`, `deletion_reviewed`, `deletion_finalized`,
  `profile_updated`. `finalize_due_deletions`/`purge_deletion_history` Celery tasks (optional
  `celery` extra) plus a `process_deletion_requests` management command for a host with no
  worker. `dynamic_user.E003` system check for a misconfigured `DELETION_MODE`/
  `DELETION_ANONYMIZE_FUNCTION` pairing.
- **Settings-driven serializer factory** (`serializers.py`, `checks.py`): `build_serializer()` —
  `lru_cache`-identical per allowlist, hard-refuses `password`/any hash field even if explicitly
  requested, validates every field name against the resolved model. `dynamic_user.E005` system
  check catching a `DYNAMIC_USER` field allowlist that names a field the resolved model doesn't
  have. Module-level accessors wiring every `*_FIELDS` setting to the resolved models with zero
  view-layer changes required from a host that subclasses `User`/`Profile`/`Setting`.
- **Self-service DRF API** (`views.py`, `urls.py`, basePath `/api/v1/users`): six views — see own
  info, edit own profile/setting, browse others' public profiles, and the deletion-request
  request/cancel/status endpoints. `IsProfileOwner` and `IsPublicOrOwner` permission classes — a
  private profile 404s for a non-owner rather than 403ing, so its existence doesn't leak.
- **Admin DRF API** (`admin_views.py`, `urls_admin.py`, basePath `/api/v1/admin/users`): full
  read/write over every user, profile, setting, and the account-deletion review/finalize flow,
  gated by `IsDynamicUserAdmin` (`DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]`-aware).
  `CanEscalatePrivilege` rejects any admin `PATCH` touching `is_staff`/`is_superuser`/
  `is_active`/`groups`/`user_permissions` unless the caller is an actual superuser, independent of
  `ADMIN_REQUIRES_SUPERUSER`. `IsSuperUser` gate on `POST /deletion-requests/{id}/finalize/` —
  superuser-only regardless of `ADMIN_REQUIRES_SUPERUSER`, since it bypasses the deletion grace
  period entirely.
- **Jazzmin admin** (`admin.py`): `User`/`Profile`/`Setting`/`AccountDeletionRequest` registrations
  with approve/reject actions on deletion requests, gated by the same admin posture switch as the
  DRF admin surface.
- **`fa` locale catalog** (`locale/fa/LC_MESSAGES/django.po`/`.mo`) for the Django-admin-facing
  surface — model `verbose_name`/`help_text`, `Meta.verbose_name`/`verbose_name_plural`,
  `AccountDeletionRequest.Status` labels, and `admin.py`'s action descriptions/messages. Matches
  `cleanup_app`'s own precedent: the DRF/API-layer surface is not translated.
- **Frontend SDK** (`@hjtdev/django-dynamic-user`, `frontend/`): 20 typed React hooks over both API
  surfaces — 10 self-service (`useMe`, `useMyProfile`, `useUpdateMyProfile`, `useMySetting`,
  `useUpdateMySetting`, `usePublicProfiles`, `usePublicProfile`, `useMyDeletionRequest`,
  `useRequestDeletion`, `useCancelDeletionRequest`) and 10 admin (`useAdminUsers`, `useAdminUser`,
  `useUpdateAdminUser`, `useAdminUserProfile`, `useUpdateAdminUserProfile`, `useAdminUserSetting`,
  `useUpdateAdminUserSetting`, `useAdminDeletionRequests`, `useReviewDeletionRequest`,
  `useFinalizeDeletionRequest`) — plus `dynamicUserKeys`/`dynamicUserAdminKeys` query-key
  factories, generated from `backend/schema.yml` via `openapi-typescript`. Types only against
  `@hjtdev/appkit`'s shared `HttpClient`/`ApiClientProvider`/`useApiClient` — no bundled client;
  `react`, `@tanstack/react-query`, and `@hjtdev/appkit` are `peerDependencies` only. Every
  destructive/admin mutation hook is proven, by test, never to fire on mount or a passive render.
- **Playground** (`playground/`, dev-only, not published): a two-host verification harness —
  `playground/default` runs this app's own concrete models with `hard_delete` and the Celery
  finalize path; `playground/subclassed` runs a host's `core.User`/`Profile`/`Setting`
  subclasses with `anonymize` and the management-command finalize path — proving the subclassed
  host's extra field round-trips over real HTTP with zero package-level code changes.
- **CI** (`.github/workflows/ci.yml`): the org-level reusable-workflow caller
  (`docs/APP-DESIGN.md` §10.2), `package-name: dynamic_user`, 85% coverage gate, both `celery` and
  `avatar` extras exercised, `publish-npm: true`, plus this repo's own `publish-pypi` job.

### Host action

Every item below is a real installation requirement, not an upgrade note — there is no prior
version to upgrade from, but a fresh install needs all four. Each is documented in full in
`README.md`'s config block; this list exists so they're findable in one place.

- Add all 14 throttle scopes to `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`: six self-service
  (`dynamic_user_me`, `dynamic_user_profile_retrieve`, `dynamic_user_profiles_list`,
  `dynamic_user_profile_update`, `dynamic_user_setting_update`, `dynamic_user_deletion_request`)
  and eight admin (`dynamic_user_admin_users_list`, `dynamic_user_admin_user_retrieve`,
  `dynamic_user_admin_user_update`, `dynamic_user_admin_profile_update`,
  `dynamic_user_admin_setting_update`, `dynamic_user_admin_deletions_list`,
  `dynamic_user_admin_deletion_review`, `dynamic_user_admin_deletion_finalize`). Without them,
  every request to these endpoints raises at request time.
- Wire `appkit`'s request-id middleware, `standard_exception_handler`, and `DefaultPagination`
  into `MIDDLEWARE`/`REST_FRAMEWORK`.
- Wire **two** `basePaths` entries on `ApiClientProvider`, not one — `dynamic_user` →
  `/api/v1/users` (self-service) and `dynamic_user_admin` → `/api/v1/admin/users` (admin). A host
  that wires only `dynamic_user` will see every admin hook 404 or hit the self-service prefix
  instead.
- `DYNAMIC_USER["DELETION_MODE"] = "anonymize"` requires `DELETION_ANONYMIZE_FUNCTION` set, or
  `DeletionService.finalize()` raises `ImproperlyConfigured` — irrelevant to a host using the
  default `DELETION_MODE`, but confirm before relying on anonymize mode in production.
