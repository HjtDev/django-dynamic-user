import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useUpdateMyProfile } from "../../frontend/src/hooks/useUpdateMyProfile.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeMyProfile } from "./fixtures.js";

const PROFILE_URL = `${TEST_BASE_URL}/api/v1/users/me/profile/`;

describe("useUpdateMyProfile", () => {
  it("updates the caller's profile on success", async () => {
    const body = makeMyProfile({ bio: "updated" });
    let receivedBody: unknown;
    server.use(
      http.patch(PROFILE_URL, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body);
      }),
    );

    const { result } = renderHook(() => useUpdateMyProfile(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ bio: "updated" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ bio: "updated" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.patch(PROFILE_URL, () => new HttpResponse(null, { status: 400 })));

    const { result } = renderHook(() => useUpdateMyProfile(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ bio: "updated" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
