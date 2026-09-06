// Hand-written, and the SDK's entire public type surface — re-exports narrowed aliases from
// schema.d.ts (generated, never hand-edited) plus everything the schema can't express. The
// manager and hooks import from here, never from ./schema.d.ts directly.
//
// The component names referenced below (MeUser, AdminProfile, PublicProfile, ...) are pinned,
// human-readable literals set on the backend's serializer accessors via
// dynamic_user.serializers._with_component_name — not build_serializer()'s own content-hashed
// class names (docs/APP-DESIGN.md §12's "unstable component name" warning). They stay fixed
// across a host's DYNAMIC_USER field-allowlist edits, so these aliases don't churn either.

import type { components, operations } from "./schema.js";

// --- self-service entities ---------------------------------------------------------------

/** `GET /me/` — USER_READ_FIELDS-shaped, entirely read-only. */
export type User = components["schemas"]["MeUser"];

/** `PATCH /me/`'s request body — v1.1.0. USER_SELF_EDITABLE_FIELDS minus USER_LOCKED_FIELDS,
 * default just `name`. */
export type UpdateMeInput = components["schemas"]["PatchedMeUserUpdateRequest"];

/** `GET /me/profile/` — the union of PROFILE_EDITABLE_FIELDS and PROFILE_READ_FIELDS. */
export type MyProfile = components["schemas"]["MeProfile"];

/** `PATCH /me/profile/`'s request body — PROFILE_EDITABLE_FIELDS only. */
export type UpdateMyProfileInput = components["schemas"]["PatchedMeProfileUpdateRequest"];

/** `GET /me/setting/` — the union of SETTING_EDITABLE_FIELDS and SETTING_READ_FIELDS. */
export type MySetting = components["schemas"]["MeSetting"];

/** `PATCH /me/setting/`'s request body — SETTING_EDITABLE_FIELDS only. */
export type UpdateMySettingInput = components["schemas"]["PatchedMeSettingUpdateRequest"];

/** `USER_PUBLIC_FIELDS`-shaped — the nested `user` block on a `PublicProfile`. */
export type PublicUser = components["schemas"]["PublicUser"];

/** `GET /profiles/`, `GET /profiles/{id}/` — PROFILE_PUBLIC_FIELDS plus a nested `PublicUser`. */
export type PublicProfile = components["schemas"]["PublicProfile"];

/** `GET /profiles/` response. */
export type PaginatedPublicProfileList = components["schemas"]["PaginatedPublicProfileList"];

/** `GET /profiles/`'s query params — `page`/`page_size`. */
export type PublicProfilesParams = NonNullable<
  operations["users_profiles_list"]["parameters"]["query"]
>;

/** `GET`/`POST` responses on `/me/deletion-request/` — entirely read-only, no `user`/`reviewed_by`. */
export type DeletionRequest = components["schemas"]["DeletionRequest"];

/** `POST /me/deletion-request/`'s request body — the only field a caller may supply. */
export type RequestDeletionInput = components["schemas"]["DeletionRequestCreateRequest"];

// --- admin entities ------------------------------------------------------------------------

/** Every real field on the resolved user model except `password` — the admin full-fields shape. */
export type AdminUser = components["schemas"]["AdminUser"];

/** `PATCH /{id}/`'s request body — any user field except `password`. Privileged keys
 * (`is_active`/`is_staff`/`is_superuser`/`groups`/`user_permissions`) are accepted here but
 * rejected server-side by `CanEscalatePrivilege` unless the caller is an actual superuser. */
export type UpdateAdminUserInput = components["schemas"]["PatchedAdminUserRequest"];

/** `GET /` response. */
export type PaginatedAdminUserList = components["schemas"]["PaginatedAdminUserList"];

/** `GET /`'s query params — `page`/`page_size` plus whatever exact-match field filters the
 * *resolved* user model exposes (`_filterable_user_fields()`, backend/src/dynamic_user/
 * admin_views.py). That set is host-dependent — a subclassed User model adds its own
 * filterable fields — so it can never be a fixed OpenAPI-declared union; this type stays
 * intentionally open beyond the two params the schema does declare. */
export type AdminUsersParams = NonNullable<operations["admin_users_list"]["parameters"]["query"]> &
  Record<string, string | number | boolean | undefined>;

/** Every real field on the resolved Profile model — the admin full-fields shape. `user` is
 * read-only (an admin PATCH can't re-point one user's Profile row onto another account). */
export type AdminProfile = components["schemas"]["AdminProfile"];

/** `PATCH /{id}/profile/`'s request body — any Profile field. */
export type UpdateAdminProfileInput = components["schemas"]["PatchedAdminProfileRequest"];

/** Every real field on the resolved Setting model — the admin full-fields shape. `user` is
 * read-only, same reasoning as `AdminProfile`. */
export type AdminSetting = components["schemas"]["AdminSetting"];

/** `PATCH /{id}/setting/`'s request body — any Setting field. */
export type UpdateAdminSettingInput = components["schemas"]["PatchedAdminSettingRequest"];

/** `GET /deletion-requests/`, and the response body of the review/finalize actions — includes
 * `user`/`reviewed_by`, unlike the self-service `DeletionRequest`. */
export type AdminDeletionRequest = components["schemas"]["AdminDeletionRequest"];

/** `GET /deletion-requests/` response. */
export type PaginatedAdminDeletionRequestList =
  components["schemas"]["PaginatedAdminDeletionRequestList"];

/** `GET /deletion-requests/`'s query params — `page`/`page_size` plus the `status` filter,
 * schema-declared (backend/src/dynamic_user/admin_views.py's `AdminDeletionRequestListView`),
 * so no hand-extension is needed here. */
export type AdminDeletionRequestsParams = NonNullable<
  operations["admin_users_deletion_requests_list"]["parameters"]["query"]
>;

/** `POST /deletion-requests/{id}/review/`'s request body. */
export type ReviewDeletionInput = components["schemas"]["DeletionReviewRequest"];

/** `AccountDeletionRequest.status` — one of `StatusEnum`'s four values. */
export type DeletionStatus = components["schemas"]["StatusEnum"];

// --- v1.1.0: admin parity additions ---------------------------------------------------------

/** `POST /`'s request body — any user field, plus an optional write-only `password`
 * (unset -> `set_unusable_password()`). Privileged keys are accepted here but rejected
 * server-side by `CanEscalatePrivilege` unless the caller is an actual superuser, same as
 * {@link UpdateAdminUserInput}. */
export type CreateAdminUserInput = components["schemas"]["AdminUserCreateRequest"];

/** `POST /{id}/set-password/`'s request body. Superuser-only, always, server-side. */
export type SetAdminUserPasswordInput = components["schemas"]["AdminSetPasswordRequest"];

/** `GET /profiles/` (admin collection) response. */
export type PaginatedAdminProfileList = components["schemas"]["PaginatedAdminProfileList"];

/** `GET /profiles/` (admin collection)'s query params — `page`/`page_size` plus whatever
 * exact-match field filters the *resolved* Profile model exposes
 * (`_filterable_model_fields()`, backend/src/dynamic_user/admin_views.py) — same open-ended
 * shape as {@link AdminUsersParams}, for the same reason. */
export type AdminProfilesParams = NonNullable<
  operations["admin_users_profiles_list"]["parameters"]["query"]
> &
  Record<string, string | number | boolean | undefined>;

/** `POST /profiles/`'s request body — any Profile field, including `user` (writable here only —
 * naming which user this new row belongs to is the entire point of a create call). */
export type CreateAdminProfileInput = components["schemas"]["AdminProfileCreateRequest"];

/** `GET /settings/` (admin collection) response. */
export type PaginatedAdminSettingList = components["schemas"]["PaginatedAdminSettingList"];

/** `GET /settings/` (admin collection)'s query params — same shape as
 * {@link AdminProfilesParams}, for Setting. */
export type AdminSettingsParams = NonNullable<
  operations["admin_users_settings_list"]["parameters"]["query"]
> &
  Record<string, string | number | boolean | undefined>;

/** `POST /settings/`'s request body — any Setting field, including `user`. */
export type CreateAdminSettingInput = components["schemas"]["AdminSettingCreateRequest"];

/** `ChangeLogEntry` (this app's own audit-log model) — entirely read-only. */
export type AdminChangeLogEntry = components["schemas"]["AdminChangeLogEntry"];

/** `GET /change-log/` response. */
export type PaginatedAdminChangeLogEntryList =
  components["schemas"]["PaginatedAdminChangeLogEntryList"];

/** `GET /change-log/`'s query params — `page`/`page_size` plus `content_type`/`object_id`/
 * `actor`/`field_name`, validated by `safe_filter_kwargs`'s own allowlist server-side
 * (not schema-declared — same open-ended shape as {@link AdminProfilesParams}). */
export type AdminChangeLogParams = NonNullable<
  operations["admin_users_change_log_list"]["parameters"]["query"]
> &
  Record<string, string | number | boolean | undefined>;

/** Django's own `django.contrib.admin.models.LogEntry` — entirely read-only. Only meaningful
 * (and only ever populated with hooks/routes) when `django.contrib.admin` is installed on the
 * backend. */
export type AdminLogEntry = components["schemas"]["AdminLogEntry"];

/** `GET /log-entries/` response. */
export type PaginatedAdminLogEntryList = components["schemas"]["PaginatedAdminLogEntryList"];

/** `GET /log-entries/`'s query params — `page`/`page_size` plus `action_flag`/`user`/
 * `content_type`, same open-ended shape as {@link AdminChangeLogParams}. */
export type AdminLogEntriesParams = NonNullable<
  operations["admin_users_log_entries_list"]["parameters"]["query"]
> &
  Record<string, string | number | boolean | undefined>;

/** `django.contrib.auth.models.Group` — read-only, populates the picker behind
 * {@link UpdateAdminUserInput}'s `groups` field. */
export type AdminGroup = components["schemas"]["AdminGroup"];

/** `GET /groups/` response. */
export type PaginatedAdminGroupList = components["schemas"]["PaginatedAdminGroupList"];

/** `django.contrib.auth.models.Permission` — read-only, populates the picker behind
 * {@link UpdateAdminUserInput}'s `user_permissions` field. */
export type AdminPermission = components["schemas"]["AdminPermission"];

/** `GET /permissions/` response. */
export type PaginatedAdminPermissionList = components["schemas"]["PaginatedAdminPermissionList"];

/** `POST /deletion-requests/`'s request body — `{user, reason}`. An admin filing a deletion
 * request on a user's behalf; unlike hand-creating one through Django Admin's own change form,
 * respects the same duplicate guard, `finalize_at` computation, and `deletion_requested` signal
 * every other creation path gets. */
export type CreateAdminDeletionRequestInput =
  components["schemas"]["AdminDeletionRequestCreateRequest"];

// appkit owns the HttpClient interface; re-exported for convenience, never redeclared.
export type { HttpClient } from "@hjtdev/appkit";
