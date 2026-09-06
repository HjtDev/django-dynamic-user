import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useDeleteAdminProfile } from "../../frontend/src/hooks/useDeleteAdminProfile.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";

const profileUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/profiles/${id}/`;

describe("useDeleteAdminProfile", () => {
  it("deletes a profile on success", async () => {
    server.use(http.delete(profileUrl(3), () => new HttpResponse(null, { status: 204 })));

    const { result } = renderHook(() => useDeleteAdminProfile(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(3);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.delete(profileUrl(3), () => new HttpResponse(null, { status: 403 })));

    const { result } = renderHook(() => useDeleteAdminProfile(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(3);

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
