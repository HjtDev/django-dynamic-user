import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useCreateAdminUser } from "../../frontend/src/hooks/useCreateAdminUser.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminUser } from "./fixtures.js";

const USERS_URL = `${TEST_BASE_URL}/api/v1/admin/users/`;

describe("useCreateAdminUser", () => {
  it("creates a user on success", async () => {
    const body = makeAdminUser({ username: "created" });
    let receivedBody: unknown;
    server.use(
      http.post(USERS_URL, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body, { status: 201 });
      }),
    );

    const { result } = renderHook(() => useCreateAdminUser(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ username: "created", email: "created@example.com" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ username: "created", email: "created@example.com" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.post(USERS_URL, () => new HttpResponse(null, { status: 403 })));

    const { result } = renderHook(() => useCreateAdminUser(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ username: "x" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
