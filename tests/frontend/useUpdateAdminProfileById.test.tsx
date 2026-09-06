import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useUpdateAdminProfileById } from "../../frontend/src/hooks/useUpdateAdminProfileById.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminProfile } from "./fixtures.js";

const profileUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/profiles/${id}/`;

describe("useUpdateAdminProfileById", () => {
  it("updates a profile by its own pk on success", async () => {
    const body = makeAdminProfile({ id: 3, bio: "updated" });
    let receivedBody: unknown;
    server.use(
      http.patch(profileUrl(3), async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body);
      }),
    );

    const { result } = renderHook(() => useUpdateAdminProfileById(3), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ bio: "updated" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ bio: "updated" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.patch(profileUrl(3), () => new HttpResponse(null, { status: 400 })));

    const { result } = renderHook(() => useUpdateAdminProfileById(3), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ bio: "updated" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
