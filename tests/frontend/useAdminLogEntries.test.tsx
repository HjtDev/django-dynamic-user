import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminLogEntries } from "../../frontend/src/hooks/useAdminLogEntries.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminLogEntryList } from "./fixtures.js";

const LOG_ENTRIES_URL = `${TEST_BASE_URL}/api/v1/admin/users/log-entries/`;

describe("useAdminLogEntries", () => {
  it("returns the paginated log-entry list on success", async () => {
    const body = makePaginatedAdminLogEntryList();
    server.use(http.get(LOG_ENTRIES_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminLogEntries(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("sends page/page_size plus a host-defined filter field as a query string", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(LOG_ENTRIES_URL, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makePaginatedAdminLogEntryList());
      }),
    );

    renderHook(() => useAdminLogEntries({ page: 1, action_flag: 2 }), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(observedUrl).toBeDefined());
    expect(observedUrl).toBe(`${LOG_ENTRIES_URL}?page=1&action_flag=2`);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(LOG_ENTRIES_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAdminLogEntries(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
