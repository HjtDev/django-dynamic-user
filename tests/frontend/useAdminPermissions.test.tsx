import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminPermissions } from "../../frontend/src/hooks/useAdminPermissions.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminPermissionList } from "./fixtures.js";

const PERMISSIONS_URL = `${TEST_BASE_URL}/api/v1/admin/users/permissions/`;

describe("useAdminPermissions", () => {
  it("returns the paginated permission list on success", async () => {
    const body = makePaginatedAdminPermissionList();
    server.use(http.get(PERMISSIONS_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminPermissions(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(PERMISSIONS_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAdminPermissions(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
