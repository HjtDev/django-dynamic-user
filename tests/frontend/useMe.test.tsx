import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useMe } from "../../frontend/src/hooks/useMe.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeUser } from "./fixtures.js";

const ME_URL = `${TEST_BASE_URL}/api/v1/users/me/`;

describe("useMe", () => {
  it("returns the current user on success", async () => {
    const body = makeUser();
    server.use(http.get(ME_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces an error on a failed request", async () => {
    server.use(http.get(ME_URL, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useMe(), { wrapper: createWrapper().Wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
