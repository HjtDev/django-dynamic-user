import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useCreateAdminSetting } from "../../frontend/src/hooks/useCreateAdminSetting.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminSetting } from "./fixtures.js";

const SETTINGS_URL = `${TEST_BASE_URL}/api/v1/admin/users/settings/`;

describe("useCreateAdminSetting", () => {
  it("creates a setting on success", async () => {
    const body = makeAdminSetting({ user: 5 });
    let receivedBody: unknown;
    server.use(
      http.post(SETTINGS_URL, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body, { status: 201 });
      }),
    );

    const { result } = renderHook(() => useCreateAdminSetting(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ user: 5, language: "fa" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ user: 5, language: "fa" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.post(SETTINGS_URL, () => new HttpResponse(null, { status: 400 })));

    const { result } = renderHook(() => useCreateAdminSetting(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ user: 5 });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
