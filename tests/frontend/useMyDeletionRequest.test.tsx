import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useMyDeletionRequest } from "../../frontend/src/hooks/useMyDeletionRequest.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeDeletionRequest } from "./fixtures.js";

const DELETION_REQUEST_URL = `${TEST_BASE_URL}/api/v1/users/me/deletion-request/`;

describe("useMyDeletionRequest", () => {
  it("returns the caller's deletion request on success", async () => {
    const body = makeDeletionRequest();
    server.use(http.get(DELETION_REQUEST_URL, () => HttpResponse.json(body)));

    const { result } = renderHook(() => useMyDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces a 404 (no request exists) as an error", async () => {
    server.use(http.get(DELETION_REQUEST_URL, () => new HttpResponse(null, { status: 404 })));

    const { result } = renderHook(() => useMyDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
