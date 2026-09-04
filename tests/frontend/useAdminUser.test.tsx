import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminUser } from "../../frontend/src/hooks/useAdminUser.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminUser } from "./fixtures.js";

const USER_URL = `${TEST_BASE_URL}/api/v1/admin/users/42/`;

describe("useAdminUser", () => {
  it("returns one user on success", async () => {
    const body = makeAdminUser({ id: 42 });
    server.use(http.get(USER_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminUser(42), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(USER_URL, () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useAdminUser(42), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
