import type {
  AdminDeletionRequestsParams,
  AdminUsersParams,
  PublicProfilesParams,
} from "../types.js";

/**
 * Exported from src/index.ts — a host sometimes needs to invalidate this app's cache from its
 * own composed code (docs/CONTRACT.md §7).
 *
 * `publicProfiles(params)`/`users(params)`/`deletionRequests(params)` deliberately drop the
 * `params` slot from the key entirely when called with no argument, rather than emitting
 * `[...all, "profiles", undefined]`. React Query's `invalidateQueries` matches by prefix with
 * partial deep equality — a length-N key ending in a literal `undefined` would compare that
 * `undefined` against every filtered query's own `{page, page_size}` object and never match,
 * silently defeating every `invalidateQueries({ queryKey: dynamicUserKeys.publicProfiles() })`-
 * style call a mutation hook makes. See tests/frontend/invalidation.test.tsx for the regression
 * this guards against — and docs/CONTRACT.md §10's deviations register for why the illustrative
 * §7 code block reads this way rather than the flat `[...all, "profiles", params]` form.
 */
export const dynamicUserKeys = {
  all: ["dynamic_user"] as const,
  me: () => [...dynamicUserKeys.all, "me"] as const,
  myProfile: () => [...dynamicUserKeys.all, "profile"] as const,
  mySetting: () => [...dynamicUserKeys.all, "setting"] as const,
  publicProfiles: (params?: PublicProfilesParams) =>
    params === undefined
      ? ([...dynamicUserKeys.all, "profiles"] as const)
      : ([...dynamicUserKeys.all, "profiles", params] as const),
  publicProfile: (id: number) => [...dynamicUserKeys.all, "profiles", id] as const,
  myDeletionRequest: () => [...dynamicUserKeys.all, "deletion-request"] as const,
};

/**
 * Under a separate root (`"dynamic_user_admin"`, not `"dynamic_user"`) from
 * {@link dynamicUserKeys} on purpose — an admin mutation invalidates only this factory's keys,
 * never the self-service surface's (docs/CONTRACT.md §7's cross-surface invalidation decision:
 * an admin editing user 42 has no reason to bust the current operator's own self-service cache,
 * and there is no reliable way to target "that other user's session" from a mutation's own
 * `onSuccess` anyway). Sharing one root array between the two factories would silently collapse
 * that boundary.
 */
export const dynamicUserAdminKeys = {
  all: ["dynamic_user_admin"] as const,
  users: (params?: AdminUsersParams) =>
    params === undefined
      ? ([...dynamicUserAdminKeys.all, "users"] as const)
      : ([...dynamicUserAdminKeys.all, "users", params] as const),
  user: (id: number) => [...dynamicUserAdminKeys.all, "users", id] as const,
  userProfile: (id: number) => [...dynamicUserAdminKeys.all, "users", id, "profile"] as const,
  userSetting: (id: number) => [...dynamicUserAdminKeys.all, "users", id, "setting"] as const,
  deletionRequests: (params?: AdminDeletionRequestsParams) =>
    params === undefined
      ? ([...dynamicUserAdminKeys.all, "deletion-requests"] as const)
      : ([...dynamicUserAdminKeys.all, "deletion-requests", params] as const),
  deletionRequest: (id: number) => [...dynamicUserAdminKeys.all, "deletion-requests", id] as const,
};
