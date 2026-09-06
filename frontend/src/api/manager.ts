// Two instance-based managers — the ONLY place a raw HTTP call happens in this SDK. Neither is
// exported from src/index.ts; a host only ever reaches them indirectly, through a hook.

import type { HttpClient } from "@hjtdev/appkit";
import type {
  AdminChangeLogEntry,
  AdminChangeLogParams,
  AdminDeletionRequest,
  AdminDeletionRequestsParams,
  AdminGroup,
  AdminLogEntriesParams,
  AdminLogEntry,
  AdminProfile,
  AdminProfilesParams,
  AdminSetting,
  AdminSettingsParams,
  AdminUser,
  AdminUsersParams,
  CreateAdminDeletionRequestInput,
  CreateAdminProfileInput,
  CreateAdminSettingInput,
  CreateAdminUserInput,
  DeletionRequest,
  MyProfile,
  MySetting,
  PaginatedAdminChangeLogEntryList,
  PaginatedAdminDeletionRequestList,
  PaginatedAdminGroupList,
  PaginatedAdminLogEntryList,
  PaginatedAdminPermissionList,
  PaginatedAdminProfileList,
  PaginatedAdminSettingList,
  PaginatedAdminUserList,
  PaginatedPublicProfileList,
  PublicProfile,
  PublicProfilesParams,
  RequestDeletionInput,
  ReviewDeletionInput,
  SetAdminUserPasswordInput,
  UpdateAdminProfileInput,
  UpdateAdminSettingInput,
  UpdateAdminUserInput,
  UpdateMeInput,
  UpdateMyProfileInput,
  UpdateMySettingInput,
  User,
} from "../types.js";

/**
 * Builds a query string from a plain params object, skipping `undefined`/`null` values.
 * `HttpClient` (appkit) has no params channel of its own — `get`/`delete` take only a path and
 * `RequestInit` — so this is the one place a query string is assembled, via `URLSearchParams`
 * rather than raw template interpolation, per the frontend security checklist's "manager methods
 * never build a URL by concatenating unescaped user input" rule.
 */
function toQueryString(params: Record<string, unknown> | undefined): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

/** Self-service surface — bound to the `dynamic_user` basePath (`/api/v1/users` by default). */
export class DynamicUserManager {
  constructor(
    private readonly client: HttpClient,
    private readonly basePath: string,
  ) {}

  getMe(): Promise<User> {
    return this.client.get<User>(`${this.basePath}/me/`);
  }

  // v1.1.0. USER_SELF_EDITABLE_FIELDS minus USER_LOCKED_FIELDS — default just `name`.
  updateMe(data: UpdateMeInput): Promise<User> {
    return this.client.patch<User>(`${this.basePath}/me/`, data);
  }

  getMyProfile(): Promise<MyProfile> {
    return this.client.get<MyProfile>(`${this.basePath}/me/profile/`);
  }

  updateMyProfile(data: UpdateMyProfileInput): Promise<MyProfile> {
    return this.client.patch<MyProfile>(`${this.basePath}/me/profile/`, data);
  }

  getMySetting(): Promise<MySetting> {
    return this.client.get<MySetting>(`${this.basePath}/me/setting/`);
  }

  updateMySetting(data: UpdateMySettingInput): Promise<MySetting> {
    return this.client.patch<MySetting>(`${this.basePath}/me/setting/`, data);
  }

  listPublicProfiles(params?: PublicProfilesParams): Promise<PaginatedPublicProfileList> {
    return this.client.get<PaginatedPublicProfileList>(
      `${this.basePath}/profiles/${toQueryString(params)}`,
    );
  }

  // `id` is the target USER's id, not the Profile row's own pk (docs/CONTRACT.md §10 item 6) —
  // matches how every other self-service route on this surface addresses "the current user."
  getPublicProfile(id: number): Promise<PublicProfile> {
    return this.client.get<PublicProfile>(`${this.basePath}/profiles/${id}/`);
  }

  getMyDeletionRequest(): Promise<DeletionRequest> {
    return this.client.get<DeletionRequest>(`${this.basePath}/me/deletion-request/`);
  }

  requestDeletion(body?: RequestDeletionInput): Promise<DeletionRequest> {
    return this.client.post<DeletionRequest>(`${this.basePath}/me/deletion-request/`, body ?? {});
  }

  cancelDeletionRequest(): Promise<void> {
    return this.client.delete<void>(`${this.basePath}/me/deletion-request/`);
  }
}

/**
 * Admin surface — bound to the `dynamic_user_admin` basePath (`/api/v1/admin/users` by default).
 * Paths below collapse to the basePath root — `${basePath}/${id}/`, never
 * `${basePath}/users/${id}/` (docs/CONTRACT.md §10 item 7: the basePath is already
 * `/api/v1/admin/users`, so appending another `users/` segment would double it up and 404).
 */
export class DynamicUserAdminManager {
  constructor(
    private readonly client: HttpClient,
    private readonly basePath: string,
  ) {}

  listUsers(params?: AdminUsersParams): Promise<PaginatedAdminUserList> {
    return this.client.get<PaginatedAdminUserList>(`${this.basePath}/${toQueryString(params)}`);
  }

  // v1.1.0. CanEscalatePrivilege-gated server-side, same rule as updateUser below.
  createUser(data: CreateAdminUserInput): Promise<AdminUser> {
    return this.client.post<AdminUser>(`${this.basePath}/`, data);
  }

  getUser(id: number): Promise<AdminUser> {
    return this.client.get<AdminUser>(`${this.basePath}/${id}/`);
  }

  updateUser(id: number, data: UpdateAdminUserInput): Promise<AdminUser> {
    return this.client.patch<AdminUser>(`${this.basePath}/${id}/`, data);
  }

  // v1.1.0. Superuser-only, always, regardless of ADMIN_REQUIRES_SUPERUSER — enforced
  // server-side; this manager makes no client-side attempt to gate it.
  deleteUser(id: number): Promise<void> {
    return this.client.delete<void>(`${this.basePath}/${id}/`);
  }

  // v1.1.0. Superuser-only, always. Runs AUTH_PASSWORD_VALIDATORS server-side.
  setUserPassword(id: number, data: SetAdminUserPasswordInput): Promise<void> {
    return this.client.post<void>(`${this.basePath}/${id}/set-password/`, data);
  }

  getUserProfile(id: number): Promise<AdminProfile> {
    return this.client.get<AdminProfile>(`${this.basePath}/${id}/profile/`);
  }

  updateUserProfile(id: number, data: UpdateAdminProfileInput): Promise<AdminProfile> {
    return this.client.patch<AdminProfile>(`${this.basePath}/${id}/profile/`, data);
  }

  getUserSetting(id: number): Promise<AdminSetting> {
    return this.client.get<AdminSetting>(`${this.basePath}/${id}/setting/`);
  }

  updateUserSetting(id: number, data: UpdateAdminSettingInput): Promise<AdminSetting> {
    return this.client.patch<AdminSetting>(`${this.basePath}/${id}/setting/`, data);
  }

  listDeletionRequests(
    params?: AdminDeletionRequestsParams,
  ): Promise<PaginatedAdminDeletionRequestList> {
    return this.client.get<PaginatedAdminDeletionRequestList>(
      `${this.basePath}/deletion-requests/${toQueryString(params)}`,
    );
  }

  reviewDeletionRequest(id: number, approved: boolean): Promise<AdminDeletionRequest> {
    const body: ReviewDeletionInput = { approved };
    return this.client.post<AdminDeletionRequest>(
      `${this.basePath}/deletion-requests/${id}/review/`,
      body,
    );
  }

  // Superuser-only, always, regardless of ADMIN_REQUIRES_SUPERUSER (docs/CONTRACT.md §5) —
  // enforced server-side; this manager makes no client-side attempt to gate it.
  finalizeDeletionRequest(id: number): Promise<void> {
    return this.client.post<void>(`${this.basePath}/deletion-requests/${id}/finalize/`);
  }

  // v1.1.0. Backs the previously-unpopulated dynamicUserAdminKeys.deletionRequest(id) key.
  getDeletionRequest(id: number): Promise<AdminDeletionRequest> {
    return this.client.get<AdminDeletionRequest>(`${this.basePath}/deletion-requests/${id}/`);
  }

  // v1.1.0. Respects the same duplicate guard, finalize_at computation, and
  // deletion_requested signal every other creation path gets (DeletionService.request).
  createDeletionRequest(data: CreateAdminDeletionRequestInput): Promise<AdminDeletionRequest> {
    return this.client.post<AdminDeletionRequest>(`${this.basePath}/deletion-requests/`, data);
  }

  // v1.1.0. A PENDING or APPROVED request only — 409 if already REJECTED/FINALIZED.
  cancelDeletionRequest(id: number): Promise<void> {
    return this.client.delete<void>(`${this.basePath}/deletion-requests/${id}/`);
  }

  // v1.1.0. The admin *collection* Django Admin's own ProfileAdmin changelist already provided
  // — not restricted to is_public=True, unlike the self-service GET /profiles/.
  listProfiles(params?: AdminProfilesParams): Promise<PaginatedAdminProfileList> {
    return this.client.get<PaginatedAdminProfileList>(
      `${this.basePath}/profiles/${toQueryString(params)}`,
    );
  }

  // v1.1.0. `user` is writable here (unlike updateProfile below) — naming which user this new
  // row belongs to is the entire point of a create call.
  createProfile(data: CreateAdminProfileInput): Promise<AdminProfile> {
    return this.client.post<AdminProfile>(`${this.basePath}/profiles/`, data);
  }

  // v1.1.0. Keyed by the Profile row's own pk, not the owning user's id — see getUserProfile
  // above for the per-user route this complements, not replaces.
  getProfile(profileId: number): Promise<AdminProfile> {
    return this.client.get<AdminProfile>(`${this.basePath}/profiles/${profileId}/`);
  }

  updateProfile(profileId: number, data: UpdateAdminProfileInput): Promise<AdminProfile> {
    return this.client.patch<AdminProfile>(`${this.basePath}/profiles/${profileId}/`, data);
  }

  deleteProfile(profileId: number): Promise<void> {
    return this.client.delete<void>(`${this.basePath}/profiles/${profileId}/`);
  }

  // v1.1.0. Same shape as listProfiles, for Setting.
  listSettings(params?: AdminSettingsParams): Promise<PaginatedAdminSettingList> {
    return this.client.get<PaginatedAdminSettingList>(
      `${this.basePath}/settings/${toQueryString(params)}`,
    );
  }

  createSetting(data: CreateAdminSettingInput): Promise<AdminSetting> {
    return this.client.post<AdminSetting>(`${this.basePath}/settings/`, data);
  }

  getSetting(settingId: number): Promise<AdminSetting> {
    return this.client.get<AdminSetting>(`${this.basePath}/settings/${settingId}/`);
  }

  updateSetting(settingId: number, data: UpdateAdminSettingInput): Promise<AdminSetting> {
    return this.client.patch<AdminSetting>(`${this.basePath}/settings/${settingId}/`, data);
  }

  deleteSetting(settingId: number): Promise<void> {
    return this.client.delete<void>(`${this.basePath}/settings/${settingId}/`);
  }

  // v1.1.0. HistoryMixin's own audit trail — previously readable only through Django Admin's
  // ChangeLogEntryAdmin.
  listChangeLog(params?: AdminChangeLogParams): Promise<PaginatedAdminChangeLogEntryList> {
    return this.client.get<PaginatedAdminChangeLogEntryList>(
      `${this.basePath}/change-log/${toQueryString(params)}`,
    );
  }

  getChangeLogEntry(id: number): Promise<AdminChangeLogEntry> {
    return this.client.get<AdminChangeLogEntry>(`${this.basePath}/change-log/${id}/`);
  }

  // v1.1.0. Superuser-only, always — an audit row deleted by anything less is exactly the
  // tampering an audit trail exists to make visible.
  deleteChangeLogEntry(id: number): Promise<void> {
    return this.client.delete<void>(`${this.basePath}/change-log/${id}/`);
  }

  // v1.1.0. Django's own django.contrib.admin.models.LogEntry — every write made through Django
  // Admin is auto-logged here already; this is the read side for a custom dashboard. Only ever
  // populated (and only reachable at all — the backend wires no route otherwise) when
  // django.contrib.admin is installed.
  listLogEntries(params?: AdminLogEntriesParams): Promise<PaginatedAdminLogEntryList> {
    return this.client.get<PaginatedAdminLogEntryList>(
      `${this.basePath}/log-entries/${toQueryString(params)}`,
    );
  }

  getLogEntry(id: number): Promise<AdminLogEntry> {
    return this.client.get<AdminLogEntry>(`${this.basePath}/log-entries/${id}/`);
  }

  // v1.1.0. Superuser-only, always — same reasoning as deleteChangeLogEntry.
  deleteLogEntry(id: number): Promise<void> {
    return this.client.delete<void>(`${this.basePath}/log-entries/${id}/`);
  }

  // v1.1.0. Read-only — populates the picker behind updateUser's `groups` field. Full Group
  // CRUD stays django.contrib.auth's own admin surface.
  listGroups(): Promise<PaginatedAdminGroupList> {
    return this.client.get<PaginatedAdminGroupList>(`${this.basePath}/groups/`);
  }

  getGroup(id: number): Promise<AdminGroup> {
    return this.client.get<AdminGroup>(`${this.basePath}/groups/${id}/`);
  }

  // v1.1.0. Read-only — populates the picker behind updateUser's `user_permissions` field.
  listPermissions(): Promise<PaginatedAdminPermissionList> {
    return this.client.get<PaginatedAdminPermissionList>(`${this.basePath}/permissions/`);
  }
}
