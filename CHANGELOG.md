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

### Added
- Frontend SDK (`@hjtdev/django-dynamic-user`, `frontend/`): 20 typed React hooks over both API
  surfaces — 10 self-service (`useMe`, `useMyProfile`, `useUpdateMyProfile`, `useMySetting`,
  `useUpdateMySetting`, `usePublicProfiles`, `usePublicProfile`, `useMyDeletionRequest`,
  `useRequestDeletion`, `useCancelDeletionRequest`) and 10 admin (`useAdminUsers`, `useAdminUser`,
  `useUpdateAdminUser`, `useAdminUserProfile`, `useUpdateAdminUserProfile`, `useAdminUserSetting`,
  `useUpdateAdminUserSetting`, `useAdminDeletionRequests`, `useReviewDeletionRequest`,
  `useFinalizeDeletionRequest`) — plus `dynamicUserKeys`/`dynamicUserAdminKeys` query-key
  factories, generated from `backend/schema.yml` via `openapi-typescript`. Types only against
  `@hjtdev/appkit`'s shared `HttpClient`/`ApiClientProvider`/`useApiClient` — no bundled client.

  **Host action:** wire **two** `basePaths` entries on `ApiClientProvider`, not one —
  `dynamic_user` → `/api/v1/users` (self-service) and `dynamic_user_admin` →
  `/api/v1/admin/users` (admin). A host that wires only `dynamic_user` will see every admin hook
  404 or hit the self-service prefix instead.
- Admin DRF API (`admin_views.py`): full read/write over every user, profile, setting, and the
  account-deletion review/finalize flow, gated by `IsDynamicUserAdmin`
  (`DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]`-aware).
- `CanEscalatePrivilege` — rejects any admin `PATCH` touching `is_staff`/`is_superuser`/
  `is_active`/`groups`/`user_permissions` unless the caller is an actual superuser, independent
  of `ADMIN_REQUIRES_SUPERUSER`.
- `IsSuperUser` gate on `POST /deletion-requests/{id}/finalize/` — superuser-only regardless of
  `ADMIN_REQUIRES_SUPERUSER`, since it bypasses the deletion grace period entirely.
- `fa` locale catalog (`locale/fa/LC_MESSAGES/django.po`/`.mo`) for the Django-admin-facing
  surface — model `verbose_name`/`help_text`, `Meta.verbose_name`/`verbose_name_plural`,
  `AccountDeletionRequest.Status` labels, and `admin.py`'s action descriptions/messages. Matches
  `cleanup_app`'s own precedent: the DRF/API-layer surface is not translated.

### Changed
- `views_admin.py` (a Phase 1 stub, never wired to anything) removed — the DRF admin API lives in
  `admin_views.py`, per `docs/APP-DESIGN.md` §5 and `docs/CONTRACT.md` §10 item 16.
- `get_admin_profile_serializer()`/`get_admin_setting_serializer()` now pin `user` read-only —
  still a full-fields `build_serializer()` call, but an admin `PATCH` can no longer reassign a
  Profile/Setting row's owner (`docs/CONTRACT.md` §10 item 17).
- Every serializer accessor wired to a `views.py`/`admin_views.py` schema call now emits a pinned,
  human-readable OpenAPI component name (`MeUser`, `AdminProfile`, `PublicProfile`, ...) instead
  of `build_serializer()`'s content-hashed class name — the shipped `frontend/src/schema.d.ts`
  type names no longer churn when a host edits a `DYNAMIC_USER` field allowlist
  (`docs/CONTRACT.md` §10 item 20). Not a `Host action`: nothing published these hashed names
  before this release, so no host code can be referencing them.
- `GET /deletion-requests/`'s `status` filter is now declared in `backend/schema.yml`
  (`docs/CONTRACT.md` §10 item 19) — was already implemented and tested, just missing from the
  OpenAPI schema, so the generated `AdminDeletionRequestsParams` type silently omitted it.

  **Host action:** add the eight `dynamic_user_admin_*` throttle scopes to
  `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`, alongside the six self-service ones already
  required since Phase 5 — `dynamic_user_admin_users_list`, `dynamic_user_admin_user_retrieve`,
  `dynamic_user_admin_user_update`, `dynamic_user_admin_profile_update`,
  `dynamic_user_admin_setting_update`, `dynamic_user_admin_deletions_list`,
  `dynamic_user_admin_deletion_review`, `dynamic_user_admin_deletion_finalize`. Without them,
  every request to the new admin endpoints raises at request time (`appkit`'s own `W004` check
  flags the gap at `manage.py check` time first, if run before the first request does).
