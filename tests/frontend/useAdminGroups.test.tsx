import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminGroups } from "../../frontend/src/hooks/useAdminGroups.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makePaginatedAdminGroupList } from "./fixtures.js";

const GROUPS_URL = `${TEST_BASE_URL}/api/v1/admin/users/groups/`;

describe("useAdminGroups", () => {
  it("returns the paginated group list on success", async () => {
    const body = makePaginatedAdminGroupList();
    server.use(http.get(GROUPS_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminGroups(), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(GROUPS_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAdminGroups(), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
