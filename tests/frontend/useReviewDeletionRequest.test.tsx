import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useReviewDeletionRequest } from "../../frontend/src/hooks/useReviewDeletionRequest.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminDeletionRequest } from "./fixtures.js";

const REVIEW_URL = `${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/7/review/`;

describe("useReviewDeletionRequest", () => {
  it("approves a pending request on success", async () => {
    const body = makeAdminDeletionRequest({ id: 7, status: "approved" });
    let receivedBody: unknown;
    server.use(
      http.post(REVIEW_URL, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(body);
      }),
    );

    const { result } = renderHook(() => useReviewDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ id: 7, approved: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(body);
    expect(receivedBody).toEqual({ approved: true });
  });

  it("surfaces a 409 (not currently pending) as an error", async () => {
    server.use(http.post(REVIEW_URL, () => new HttpResponse(null, { status: 409 })));

    const { result } = renderHook(() => useReviewDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });

    result.current.mutate({ id: 7, approved: false });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
