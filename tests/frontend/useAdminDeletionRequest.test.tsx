import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminDeletionRequest } from "../../frontend/src/hooks/useAdminDeletionRequest.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminDeletionRequest } from "./fixtures.js";

const requestUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/${id}/`;

describe("useAdminDeletionRequest", () => {
  it("returns a deletion request by id on success", async () => {
    const body = makeAdminDeletionRequest({ id: 4 });
    server.use(http.get(requestUrl(4), () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminDeletionRequest(4), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("does not fire when id is not finite", () => {
    const { result } = renderHook(() => useAdminDeletionRequest(Number.NaN), {
      wrapper: createWrapper().Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(requestUrl(4), () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useAdminDeletionRequest(4), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
