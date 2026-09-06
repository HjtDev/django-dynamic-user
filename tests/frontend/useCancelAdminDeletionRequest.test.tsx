import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useCancelAdminDeletionRequest } from "../../frontend/src/hooks/useCancelAdminDeletionRequest.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";

const requestUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/${id}/`;

describe("useCancelAdminDeletionRequest", () => {
  it("cancels a deletion request on success", async () => {
    server.use(http.delete(requestUrl(4), () => new HttpResponse(null, { status: 204 })));

    const { result } = renderHook(() => useCancelAdminDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(4);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.delete(requestUrl(4), () => new HttpResponse(null, { status: 409 })));

    const { result } = renderHook(() => useCancelAdminDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(4);

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
