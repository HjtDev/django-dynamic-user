import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminUserSetting } from "../../frontend/src/hooks/useAdminUserSetting.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminSetting } from "./fixtures.js";

const SETTING_URL = `${TEST_BASE_URL}/api/v1/admin/users/42/setting/`;

describe("useAdminUserSetting", () => {
  it("returns one user's setting on success", async () => {
    const body = makeAdminSetting({ id: 42, user: 42 });
    server.use(http.get(SETTING_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminUserSetting(42), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(SETTING_URL, () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useAdminUserSetting(42), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
