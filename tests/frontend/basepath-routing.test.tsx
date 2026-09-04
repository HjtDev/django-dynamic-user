import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useMe } from "../../frontend/src/hooks/useMe.js";
import { useAdminUsers } from "../../frontend/src/hooks/useAdminUsers.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminUserList, makeUser } from "./fixtures.js";

/**
 * Proves both basePath keys this app registers — `dynamic_user` (self-service) and
 * `dynamic_user_admin` (admin) — are each actually used to route a real request to its own
 * prefix, not just declared in api/config.ts. A host wiring only one basePath entry is a
 * documented failure mode (docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md §4); this is the test that
 * would catch this SDK routing a self-service hook at the admin prefix or vice versa.
 */
describe("both basePath keys route independently", () => {
  it("useMe (dynamic_user) hits /api/v1/users/, never the admin prefix", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(`${TEST_BASE_URL}/api/v1/users/me/`, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makeUser());
      }),
    );

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(observedUrl).toBe(`${TEST_BASE_URL}/api/v1/users/me/`);
  });

  it("useAdminUsers (dynamic_user_admin) hits /api/v1/admin/users/, never the self-service prefix", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(`${TEST_BASE_URL}/api/v1/admin/users/`, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makePaginatedAdminUserList());
      }),
    );

    const { result } = renderHook(() => useAdminUsers(), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(observedUrl).toBe(`${TEST_BASE_URL}/api/v1/admin/users/`);
  });
});
