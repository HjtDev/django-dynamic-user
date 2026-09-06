import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useSetAdminUserPassword } from "../../frontend/src/hooks/useSetAdminUserPassword.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";

const setPasswordUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/${id}/set-password/`;

describe("useSetAdminUserPassword", () => {
  it("sets a user's password on success", async () => {
    let receivedBody: unknown;
    server.use(
      http.post(setPasswordUrl(7), async ({ request }) => {
        receivedBody = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result } = renderHook(() => useSetAdminUserPassword(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ id: 7, data: { password: "brandnewpassword123" } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(receivedBody).toEqual({ password: "brandnewpassword123" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.post(setPasswordUrl(7), () => new HttpResponse(null, { status: 400 })));

    const { result } = renderHook(() => useSetAdminUserPassword(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate({ id: 7, data: { password: "123" } });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
