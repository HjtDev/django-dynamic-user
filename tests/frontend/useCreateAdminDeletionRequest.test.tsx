import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useCreateAdminDeletionRequest } from "../../frontend/src/hooks/useCreateAdminDeletionRequest.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminDeletionRequest } from "./fixtures.js";

const REQUESTS_URL = `${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/`;

describe("useCreateAdminDeletionRequest", () => {
  it("creates a deletion request on a user's behalf on success", async () => {
    const body = makeAdminDeletionRequest({ user: 8 });
    let receivedBody: unknown;
    server.use(
      http.post(REQUESTS_URL, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body, { status: 201 });
      }),
    );

    const { result } = renderHook(() => useCreateAdminDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ user: 8, reason: "admin-filed" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ user: 8, reason: "admin-filed" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.post(REQUESTS_URL, () => new HttpResponse(null, { status: 409 })));

    const { result } = renderHook(() => useCreateAdminDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ user: 8, reason: "" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
