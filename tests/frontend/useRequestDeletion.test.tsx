import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useRequestDeletion } from "../../frontend/src/hooks/useRequestDeletion.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeDeletionRequest } from "./fixtures.js";

const DELETION_REQUEST_URL = `${TEST_BASE_URL}/api/v1/users/me/deletion-request/`;

describe("useRequestDeletion", () => {
  it("creates a deletion request on success", async () => {
    const body = makeDeletionRequest({ reason: "no longer needed" });
    server.use(http.post(DELETION_REQUEST_URL, () => HttpResponse.json(body, { status: 201 })));

    const { result } = renderHook(() => useRequestDeletion(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ reason: "no longer needed" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
  });

  it("surfaces a 409 (already pending) as an error", async () => {
    server.use(http.post(DELETION_REQUEST_URL, () => new HttpResponse(null, { status: 409 })));

    const { result } = renderHook(() => useRequestDeletion(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
