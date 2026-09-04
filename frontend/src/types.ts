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

// appkit owns the HttpClient interface; re-exported for convenience, never redeclared.
export type { HttpClient } from "@hjtdev/appkit";
