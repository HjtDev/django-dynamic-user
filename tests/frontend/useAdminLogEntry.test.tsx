import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminLogEntry } from "../../frontend/src/hooks/useAdminLogEntry.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminLogEntry } from "./fixtures.js";

const entryUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/log-entries/${id}/`;

describe("useAdminLogEntry", () => {
  it("returns a log entry by id on success", async () => {
    const body = makeAdminLogEntry({ id: 11 });
    server.use(http.get(entryUrl(11), () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminLogEntry(11), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("does not fire when id is not finite", () => {
    const { result } = renderHook(() => useAdminLogEntry(Number.NaN), {
      wrapper: createWrapper().Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(entryUrl(11), () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useAdminLogEntry(11), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
