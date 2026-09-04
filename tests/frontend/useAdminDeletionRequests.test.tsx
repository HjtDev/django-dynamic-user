import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminDeletionRequests } from "../../frontend/src/hooks/useAdminDeletionRequests.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminDeletionRequestList } from "./fixtures.js";

const DELETION_REQUESTS_URL = `${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/`;

describe("useAdminDeletionRequests", () => {
  it("returns the paginated deletion-request list on success", async () => {
    const body = makePaginatedAdminDeletionRequestList();
    server.use(http.get(DELETION_REQUESTS_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminDeletionRequests(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("sends the status filter as a query string", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(DELETION_REQUESTS_URL, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makePaginatedAdminDeletionRequestList());
      }),
    );

    renderHook(() => useAdminDeletionRequests({ status: "pending" }), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(observedUrl).toBeDefined());
    expect(observedUrl).toBe(`${DELETION_REQUESTS_URL}?status=pending`);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(DELETION_REQUESTS_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAdminDeletionRequests(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
