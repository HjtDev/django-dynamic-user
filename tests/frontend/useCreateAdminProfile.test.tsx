import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useCreateAdminProfile } from "../../frontend/src/hooks/useCreateAdminProfile.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminProfile } from "./fixtures.js";

const PROFILES_URL = `${TEST_BASE_URL}/api/v1/admin/users/profiles/`;

describe("useCreateAdminProfile", () => {
  it("creates a profile on success", async () => {
    const body = makeAdminProfile({ user: 5 });
    let receivedBody: unknown;
    server.use(
      http.post(PROFILES_URL, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body, { status: 201 });
      }),
    );

    const { result } = renderHook(() => useCreateAdminProfile(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ user: 5, bio: "hello" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ user: 5, bio: "hello" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.post(PROFILES_URL, () => new HttpResponse(null, { status: 400 })));

    const { result } = renderHook(() => useCreateAdminProfile(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ user: 5 });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
