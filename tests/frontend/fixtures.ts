import type {
  AdminDeletionRequest,
  AdminProfile,
  AdminSetting,
  AdminUser,
  DeletionRequest,
  MyProfile,
  MySetting,
  PaginatedAdminDeletionRequestList,
  PaginatedAdminUserList,
  PaginatedPublicProfileList,
  PublicProfile,
  PublicUser,
  User,
} from "../../frontend/src/types.js";

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    username: "alice",
    name: "Alice",
    email: "alice@example.com",
    phone: null,
    is_active: true,
    date_joined: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeAdminUser(overrides: Partial<AdminUser> = {}): AdminUser {
  return {
    id: 1,
    last_login: null,
    is_superuser: false,
    username: "alice",
    name: "Alice",
    email: "alice@example.com",
    phone: null,
    is_active: true,
    is_staff: false,
    date_joined: "2026-01-01T00:00:00Z",
    groups: [],
    user_permissions: [],
    ...overrides,
  };
}

export function makePublicUser(overrides: Partial<PublicUser> = {}): PublicUser {
  return {
    id: 1,
    username: "alice",
    ...overrides,
  };
}

export function makeMyProfile(overrides: Partial<MyProfile> = {}): MyProfile {
  return {
    id: 1,
    bio: "hello",
    is_public: true,
    ...overrides,
  };
}

export function makeAdminProfile(overrides: Partial<AdminProfile> = {}): AdminProfile {
  return {
    id: 1,
    user: 1,
    bio: "hello",
    is_public: true,
    ...overrides,
  };
}

export function makePublicProfile(overrides: Partial<PublicProfile> = {}): PublicProfile {
  return {
    id: 1,
    bio: "hello",
    user: makePublicUser(),
    ...overrides,
  };
}

export function makeMySetting(overrides: Partial<MySetting> = {}): MySetting {
  return {
    id: 1,
    language: "en",
    timezone: "UTC",
    notifications_enabled: true,
    ...overrides,
  };
}

export function makeAdminSetting(overrides: Partial<AdminSetting> = {}): AdminSetting {
  return {
    id: 1,
    user: 1,
    language: "en",
    timezone: "UTC",
    notifications_enabled: true,
    ...overrides,
  };
}

export function makeDeletionRequest(overrides: Partial<DeletionRequest> = {}): DeletionRequest {
  return {
    id: 1,
    status: "pending",
    reason: "",
    requested_at: "2026-01-01T00:00:00Z",
    reviewed_at: null,
    finalize_at: "2026-01-15T00:00:00Z",
    ...overrides,
  };
}

export function makeAdminDeletionRequest(
  overrides: Partial<AdminDeletionRequest> = {},
): AdminDeletionRequest {
  return {
    id: 1,
    user: 1,
    status: "pending",
    reason: "",
    requested_at: "2026-01-01T00:00:00Z",
    reviewed_at: null,
    reviewed_by: null,
    finalize_at: "2026-01-15T00:00:00Z",
    ...overrides,
  };
}

export function makePaginatedPublicProfileList(
  overrides: Partial<PaginatedPublicProfileList> = {},
): PaginatedPublicProfileList {
  return {
    count: 1,
    next: null,
    previous: null,
    results: [makePublicProfile()],
    ...overrides,
  };
}

export function makePaginatedAdminUserList(
  overrides: Partial<PaginatedAdminUserList> = {},
): PaginatedAdminUserList {
  return {
    count: 1,
    next: null,
    previous: null,
    results: [makeAdminUser()],
    ...overrides,
  };
}

export function makePaginatedAdminDeletionRequestList(
  overrides: Partial<PaginatedAdminDeletionRequestList> = {},
): PaginatedAdminDeletionRequestList {
  return {
    count: 1,
    next: null,
    previous: null,
    results: [makeAdminDeletionRequest()],
    ...overrides,
  };
}
