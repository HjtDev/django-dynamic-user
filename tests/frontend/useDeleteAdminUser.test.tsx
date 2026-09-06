import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useDeleteAdminUser } from "../../frontend/src/hooks/useDeleteAdminUser.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";

const userUrl = (id: number) => `${TEST_BASE_URL}/api/v1/admin/users/${id}/`;

describe("useDeleteAdminUser", () => {
  it("deletes a user on success", async () => {
    let deletedUrl: string | undefined;
    server.use(
      http.delete(userUrl(42), ({ request }) => {
        deletedUrl = request.url;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result } = renderHook(() => useDeleteAdminUser(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(42);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(deletedUrl).toBe(userUrl(42));
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.delete(userUrl(42), () => new HttpResponse(null, { status: 403 })));

    const { result } = renderHook(() => useDeleteAdminUser(), {
      wrapper: createWrapper().Wrapper,
    });
    result.current.mutate(42);

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
