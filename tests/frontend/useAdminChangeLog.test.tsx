import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminChangeLog } from "../../frontend/src/hooks/useAdminChangeLog.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminChangeLogEntryList } from "./fixtures.js";

const CHANGE_LOG_URL = `${TEST_BASE_URL}/api/v1/admin/users/change-log/`;

describe("useAdminChangeLog", () => {
  it("returns the paginated change-log list on success", async () => {
    const body = makePaginatedAdminChangeLogEntryList();
    server.use(http.get(CHANGE_LOG_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminChangeLog(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("sends page/page_size plus a host-defined filter field as a query string", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(CHANGE_LOG_URL, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makePaginatedAdminChangeLogEntryList());
      }),
    );

    renderHook(() => useAdminChangeLog({ page: 1, field_name: "name" }), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(observedUrl).toBeDefined());
    expect(observedUrl).toBe(`${CHANGE_LOG_URL}?page=1&field_name=name`);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(CHANGE_LOG_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAdminChangeLog(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
