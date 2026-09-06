import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminProfiles } from "../../frontend/src/hooks/useAdminProfiles.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminProfileList } from "./fixtures.js";

const PROFILES_URL = `${TEST_BASE_URL}/api/v1/admin/users/profiles/`;

describe("useAdminProfiles", () => {
  it("returns the paginated admin profile list on success", async () => {
    const body = makePaginatedAdminProfileList();
    server.use(http.get(PROFILES_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminProfiles(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("sends page/page_size plus a host-defined filter field as a query string", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(PROFILES_URL, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makePaginatedAdminProfileList());
      }),
    );

    renderHook(() => useAdminProfiles({ page: 1, is_public: "true" }), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(observedUrl).toBeDefined());
    expect(observedUrl).toBe(`${PROFILES_URL}?page=1&is_public=true`);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(PROFILES_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAdminProfiles(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
