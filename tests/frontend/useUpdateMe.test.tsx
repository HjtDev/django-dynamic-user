import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useUpdateMe } from "../../frontend/src/hooks/useUpdateMe.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeUser } from "./fixtures.js";

const ME_URL = `${TEST_BASE_URL}/api/v1/users/me/`;

describe("useUpdateMe", () => {
  it("updates the caller's own name on success", async () => {
    const body = makeUser({ name: "New Name" });
    let receivedBody: unknown;
    server.use(
      http.patch(ME_URL, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body);
      }),
    );

    const { result } = renderHook(() => useUpdateMe(), { wrapper: createWrapper().Wrapper });
    result.current.mutate({ name: "New Name" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ name: "New Name" });
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.patch(ME_URL, () => new HttpResponse(null, { status: 400 })));

    const { result } = renderHook(() => useUpdateMe(), { wrapper: createWrapper().Wrapper });
    result.current.mutate({ name: "New Name" });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
