import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminGroup } from "../../frontend/src/hooks/useAdminGroup.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminGroup } from "./fixtures.js";

const groupUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/groups/${id}/`;

describe("useAdminGroup", () => {
  it("returns a group by id on success", async () => {
    const body = makeAdminGroup({ id: 2, name: "viewers" });
    server.use(http.get(groupUrl(2), () => HttpResponse.json(body)));

    const { result } = renderHook(() => useAdminGroup(2), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("does not fire when id is not finite", () => {
    const { result } = renderHook(() => useAdminGroup(Number.NaN), {
      wrapper: createWrapper().Wrapper,
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(groupUrl(2), () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useAdminGroup(2), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
