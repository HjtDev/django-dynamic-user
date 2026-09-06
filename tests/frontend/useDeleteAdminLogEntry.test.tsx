import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useDeleteAdminLogEntry } from "../../frontend/src/hooks/useDeleteAdminLogEntry.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";

const entryUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/log-entries/${id}/`;

describe("useDeleteAdminLogEntry", () => {
  it("deletes a log entry on success", async () => {
    server.use(http.delete(entryUrl(11), () => new HttpResponse(null, { status: 204 })));

    const { result } = renderHook(() => useDeleteAdminLogEntry(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(11);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.delete(entryUrl(11), () => new HttpResponse(null, { status: 403 })));

    const { result } = renderHook(() => useDeleteAdminLogEntry(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(11);

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
