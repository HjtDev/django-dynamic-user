import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminChangeLogEntry } from "../../frontend/src/hooks/useAdminChangeLogEntry.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminChangeLogEntry } from "./fixtures.js";

const entryUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/change-log/${id}/`;

describe("useAdminChangeLogEntry", () => {
  it("returns a change-log entry by id on success", async () => {
    const body = makeAdminChangeLogEntry({ id: 6 });
    server.use(http.get(entryUrl(6), () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminChangeLogEntry(6), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("does not fire when id is not finite", () => {
    const { result } = renderHook(() => useAdminChangeLogEntry(Number.NaN), {
      wrapper: createWrapper().Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(entryUrl(6), () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useAdminChangeLogEntry(6), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
