import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminSettings } from "../../frontend/src/hooks/useAdminSettings.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminSettingList } from "./fixtures.js";

const SETTINGS_URL = `${TEST_BASE_URL}/api/v1/admin/users/settings/`;

describe("useAdminSettings", () => {
  it("returns the paginated admin setting list on success", async () => {
    const body = makePaginatedAdminSettingList();
    server.use(http.get(SETTINGS_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminSettings(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("sends page/page_size plus a host-defined filter field as a query string", async () => {
    let observedUrl: string | undefined;
    server.use(
      http.get(SETTINGS_URL, ({ request }) => {
        observedUrl = request.url;
        return HttpResponse.json(makePaginatedAdminSettingList());
      }),
    );

    renderHook(() => useAdminSettings({ page: 1, language: "fa" }), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(observedUrl).toBeDefined());
    expect(observedUrl).toBe(`${SETTINGS_URL}?page=1&language=fa`);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(SETTINGS_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAdminSettings(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
