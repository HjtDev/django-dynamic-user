import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminUserProfile } from "../../frontend/src/hooks/useAdminUserProfile.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminProfile } from "./fixtures.js";

const PROFILE_URL = `${TEST_BASE_URL}/api/v1/admin/users/42/profile/`;

describe("useAdminUserProfile", () => {
  it("returns one user's profile on success", async () => {
    const body = makeAdminProfile({ id: 42, user: 42 });
    server.use(http.get(PROFILE_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminUserProfile(42), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(PROFILE_URL, () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useAdminUserProfile(42), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
