// Two instance-based managers — the ONLY place a raw HTTP call happens in this SDK. Neither is
// exported from src/index.ts; a host only ever reaches them indirectly, through a hook.

import type { HttpClient } from "@hjtdev/appkit";
import type {
  AdminDeletionRequest,
  AdminDeletionRequestsParams,
  AdminProfile,
  AdminSetting,
  AdminUser,
  AdminUsersParams,
  DeletionRequest,
  MyProfile,
  MySetting,
  PaginatedAdminDeletionRequestList,
  PaginatedAdminUserList,
  PaginatedPublicProfileList,
  PublicProfile,
  PublicProfilesParams,
  RequestDeletionInput,
  ReviewDeletionInput,
  UpdateAdminProfileInput,
  UpdateAdminSettingInput,
  UpdateAdminUserInput,
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

  getUser(id: number): Promise<AdminUser> {
    return this.client.get<AdminUser>(`${this.basePath}/${id}/`);
  }

  updateUser(id: number, data: UpdateAdminUserInput): Promise<AdminUser> {
    return this.client.patch<AdminUser>(`${this.basePath}/${id}/`, data);
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
}
