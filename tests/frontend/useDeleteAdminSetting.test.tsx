import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useDeleteAdminSetting } from "../../frontend/src/hooks/useDeleteAdminSetting.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";

const settingUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/settings/${id}/`;

describe("useDeleteAdminSetting", () => {
  it("deletes a setting on success", async () => {
    server.use(http.delete(settingUrl(3), () => new HttpResponse(null, { status: 204 })));

    const { result } = renderHook(() => useDeleteAdminSetting(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(3);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.delete(settingUrl(3), () => new HttpResponse(null, { status: 403 })));

    const { result } = renderHook(() => useDeleteAdminSetting(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(3);

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
