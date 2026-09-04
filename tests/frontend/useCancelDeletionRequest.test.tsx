import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useCancelDeletionRequest } from "../../frontend/src/hooks/useCancelDeletionRequest.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";

const DELETION_REQUEST_URL = `${TEST_BASE_URL}/api/v1/users/me/deletion-request/`;

describe("useCancelDeletionRequest", () => {
  it("cancels the caller's pending deletion request on success", async () => {
    server.use(http.delete(DELETION_REQUEST_URL, () => new HttpResponse(null, { status: 204 })));

    const { result } = renderHook(() => useCancelDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("surfaces a 409 (not currently pending) as an error", async () => {
    server.use(http.delete(DELETION_REQUEST_URL, () => new HttpResponse(null, { status: 409 })));

    const { result } = renderHook(() => useCancelDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
