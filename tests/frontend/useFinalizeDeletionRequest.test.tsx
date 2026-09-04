import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useFinalizeDeletionRequest } from "../../frontend/src/hooks/useFinalizeDeletionRequest.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";

const FINALIZE_URL = `${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/7/finalize/`;

describe("useFinalizeDeletionRequest", () => {
  it("finalizes an approved request on success", async () => {
    server.use(http.post(FINALIZE_URL, () => new HttpResponse(null, { status: 204 })));

    const { result } = renderHook(() => useFinalizeDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate(7);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("surfaces a 403 (non-superuser) as an error", async () => {
    server.use(http.post(FINALIZE_URL, () => new HttpResponse(null, { status: 403 })));

    const { result } = renderHook(() => useFinalizeDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate(7);

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
