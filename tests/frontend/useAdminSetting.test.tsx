import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminSetting } from "../../frontend/src/hooks/useAdminSetting.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminSetting } from "./fixtures.js";

const settingUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/settings/${id}/`;

describe("useAdminSetting", () => {
  it("returns a setting by its own pk on success", async () => {
    const body = makeAdminSetting({ id: 9 });
    server.use(http.get(settingUrl(9), () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminSetting(9), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("does not fire when id is not finite", () => {
    const { result } = renderHook(() => useAdminSetting(Number.NaN), {
      wrapper: createWrapper().Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(settingUrl(9), () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useAdminSetting(9), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
