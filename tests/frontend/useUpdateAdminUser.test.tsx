import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useUpdateAdminUser } from "../../frontend/src/hooks/useUpdateAdminUser.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminUser } from "./fixtures.js";

const USER_URL = `${TEST_BASE_URL}/api/v1/admin/users/42/`;

describe("useUpdateAdminUser", () => {
  it("updates a user on success", async () => {
    const body = makeAdminUser({ id: 42, name: "Renamed" });
    server.use(http.patch(USER_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useUpdateAdminUser(42), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ name: "Renamed" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces a 403 (privilege-escalation guard) as an error", async () => {
    server.use(http.patch(USER_URL, () => new HttpResponse(null, { status: 403 })));

    const { result } = renderHook(() => useUpdateAdminUser(42), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ is_staff: true });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
