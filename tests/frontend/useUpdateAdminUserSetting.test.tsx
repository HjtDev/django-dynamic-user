import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useUpdateAdminUserSetting } from "../../frontend/src/hooks/useUpdateAdminUserSetting.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminSetting } from "./fixtures.js";

const SETTING_URL = `${TEST_BASE_URL}/api/v1/admin/users/42/setting/`;

describe("useUpdateAdminUserSetting", () => {
  it("updates one user's setting on success", async () => {
    const body = makeAdminSetting({ id: 42, user: 42, language: "fa" });
    server.use(http.patch(SETTING_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useUpdateAdminUserSetting(42), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ language: "fa" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.patch(SETTING_URL, () => new HttpResponse(null, { status: 400 })));

    const { result } = renderHook(() => useUpdateAdminUserSetting(42), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ language: "fa" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
