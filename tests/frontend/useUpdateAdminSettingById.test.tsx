import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useUpdateAdminSettingById } from "../../frontend/src/hooks/useUpdateAdminSettingById.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminSetting } from "./fixtures.js";

const settingUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/settings/${id}/`;

describe("useUpdateAdminSettingById", () => {
  it("updates a setting by its own pk on success", async () => {
    const body = makeAdminSetting({ id: 3, language: "fa" });
    let receivedBody: unknown;
    server.use(
      http.patch(settingUrl(3), async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body);
      }),
    );

    const { result } = renderHook(() => useUpdateAdminSettingById(3), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ language: "fa" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ language: "fa" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.patch(settingUrl(3), () => new HttpResponse(null, { status: 400 })));

    const { result } = renderHook(() => useUpdateAdminSettingById(3), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ language: "fa" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
