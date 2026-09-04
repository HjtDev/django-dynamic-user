import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { usePublicProfiles } from "../../frontend/src/hooks/usePublicProfiles.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedPublicProfileList } from "./fixtures.js";

const PROFILES_URL = `${TEST_BASE_URL}/api/v1/users/profiles/`;

describe("usePublicProfiles", () => {
  it("returns the paginated public profile list on success", async () => {
    const body = makePaginatedPublicProfileList();
    server.use(http.get(PROFILES_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => usePublicProfiles(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("sends page/page_size as a query string", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(PROFILES_URL, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makePaginatedPublicProfileList());
      }),
    );

    renderHook(() => usePublicProfiles({ page: 2, page_size: 10 }), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(observedUrl).toBeDefined());
    expect(observedUrl).toBe(`${PROFILES_URL}?page=2&page_size=10`);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(PROFILES_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => usePublicProfiles(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
