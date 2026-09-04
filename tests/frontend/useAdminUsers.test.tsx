import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminUsers } from "../../frontend/src/hooks/useAdminUsers.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminUserList } from "./fixtures.js";

const USERS_URL = `${TEST_BASE_URL}/api/v1/admin/users/`;

describe("useAdminUsers", () => {
  it("returns the paginated admin user list on success", async () => {
    const body = makePaginatedAdminUserList();
    server.use(http.get(USERS_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminUsers(), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("sends page/page_size plus a host-defined filter field as a query string", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(USERS_URL, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makePaginatedAdminUserList());
      }),
    );

    // `is_active` isn't part of the schema-declared query type — it's an example of the
    // host-model-dependent exact-match filter AdminUsersParams intentionally stays open for.
    renderHook(() => useAdminUsers({ page: 1, is_active: "true" }), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(observedUrl).toBeDefined());
    expect(observedUrl).toBe(`${USERS_URL}?page=1&is_active=true`);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(USERS_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAdminUsers(), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
