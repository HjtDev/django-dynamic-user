import { describe, expect, it } from "vitest";
import * as mod from "../../frontend/src/index.js";

/**
 * Locks src/index.ts's public value-export surface to a hardcoded literal list — the mechanical
 * guard for docs/APP-DESIGN.md §12's "index.ts is the only entrypoint" rule. Negative assertions
 * below prove the two managers, both config hooks, and any provider are NOT exported — a
 * regression here means an internal implementation detail leaked into the published package.
 */
describe("frontend/src/index.ts public surface", () => {
  it("exports exactly the 20 hooks plus both key factories, nothing else", () => {
    const expected = [
      // self-service hooks
      "useMe",
      "useMyProfile",
      "useUpdateMyProfile",
      "useMySetting",
      "useUpdateMySetting",
      "usePublicProfiles",
      "usePublicProfile",
      "useMyDeletionRequest",
      "useRequestDeletion",
      "useCancelDeletionRequest",
      // admin hooks
      "useAdminUsers",
      "useAdminUser",
      "useUpdateAdminUser",
      "useAdminUserProfile",
      "useUpdateAdminUserProfile",
      "useAdminUserSetting",
      "useUpdateAdminUserSetting",
      "useAdminDeletionRequests",
      "useReviewDeletionRequest",
      "useFinalizeDeletionRequest",
      // key factories
      "dynamicUserKeys",
      "dynamicUserAdminKeys",
    ].sort();

    expect(Object.keys(mod).sort()).toEqual(expected);
  });

  it("never exports either manager, either config hook, or a provider", () => {
    const surface = mod as Record<string, unknown>;
    expect(surface.DynamicUserManager).toBeUndefined();
    expect(surface.DynamicUserAdminManager).toBeUndefined();
    expect(surface.useDynamicUserConfig).toBeUndefined();
    expect(surface.useDynamicUserAdminConfig).toBeUndefined();
    expect(surface.ApiClientProvider).toBeUndefined();
  });
});
