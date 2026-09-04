import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useRequestDeletion } from "../../frontend/src/hooks/useRequestDeletion.js";
import { useCancelDeletionRequest } from "../../frontend/src/hooks/useCancelDeletionRequest.js";
import { useUpdateAdminUser } from "../../frontend/src/hooks/useUpdateAdminUser.js";
import { useUpdateAdminUserProfile } from "../../frontend/src/hooks/useUpdateAdminUserProfile.js";
import { useUpdateAdminUserSetting } from "../../frontend/src/hooks/useUpdateAdminUserSetting.js";
import { useUpdateMyProfile } from "../../frontend/src/hooks/useUpdateMyProfile.js";
import { useUpdateMySetting } from "../../frontend/src/hooks/useUpdateMySetting.js";
import { useReviewDeletionRequest } from "../../frontend/src/hooks/useReviewDeletionRequest.js";
import { useFinalizeDeletionRequest } from "../../frontend/src/hooks/useFinalizeDeletionRequest.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import {
  makeAdminDeletionRequest,
  makeAdminProfile,
  makeAdminSetting,
  makeAdminUser,
  makeDeletionRequest,
  makeMyProfile,
  makeMySetting,
} from "./fixtures.js";

/**
 * Every mutation hook this SDK ships — all nine, not a sample — must never fire on mount or a
 * passive render (docs/APP-DESIGN.md §12's frontend security checklist) — react-query's own
 * contract already guarantees this for `mutationFn`, but a hook that accidentally wires the
 * mutation into a `useEffect`/render-time call would defeat it silently. Each case below: mount,
 * rerender twice, flush a microtask, and prove the handler was never hit — then call `mutate()`
 * and prove it fires exactly once.
 */
describe("irreversible mutations never fire on mount", () => {
  it("useRequestDeletion", async () => {
    let calls = 0;
    server.use(
      http.post(`${TEST_BASE_URL}/api/v1/users/me/deletion-request/`, () => {
        calls += 1;
        return HttpResponse.json(makeDeletionRequest(), { status: 201 });
      }),
    );

    const { result, rerender } = renderHook(() => useRequestDeletion(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useCancelDeletionRequest", async () => {
    let calls = 0;
    server.use(
      http.delete(`${TEST_BASE_URL}/api/v1/users/me/deletion-request/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useCancelDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useUpdateAdminUser", async () => {
    let calls = 0;
    server.use(
      http.patch(`${TEST_BASE_URL}/api/v1/admin/users/42/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminUser({ id: 42 }));
      }),
    );

    const { result, rerender } = renderHook(() => useUpdateAdminUser(42), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ name: "Renamed" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useReviewDeletionRequest", async () => {
    let calls = 0;
    server.use(
      http.post(`${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/7/review/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminDeletionRequest({ id: 7, status: "approved" }));
      }),
    );

    const { result, rerender } = renderHook(() => useReviewDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ id: 7, approved: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useFinalizeDeletionRequest", async () => {
    let calls = 0;
    server.use(
      http.post(`${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/7/finalize/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useFinalizeDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate(7);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useUpdateMyProfile", async () => {
    let calls = 0;
    server.use(
      http.patch(`${TEST_BASE_URL}/api/v1/users/me/profile/`, () => {
        calls += 1;
        return HttpResponse.json(makeMyProfile());
      }),
    );

    const { result, rerender } = renderHook(() => useUpdateMyProfile(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ bio: "updated" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useUpdateMySetting", async () => {
    let calls = 0;
    server.use(
      http.patch(`${TEST_BASE_URL}/api/v1/users/me/setting/`, () => {
        calls += 1;
        return HttpResponse.json(makeMySetting());
      }),
    );

    const { result, rerender } = renderHook(() => useUpdateMySetting(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ language: "fa" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useUpdateAdminUserProfile", async () => {
    let calls = 0;
    server.use(
      http.patch(`${TEST_BASE_URL}/api/v1/admin/users/42/profile/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminProfile({ id: 42 }));
      }),
    );

    const { result, rerender } = renderHook(() => useUpdateAdminUserProfile(42), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ bio: "updated" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useUpdateAdminUserSetting", async () => {
    let calls = 0;
    server.use(
      http.patch(`${TEST_BASE_URL}/api/v1/admin/users/42/setting/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminSetting({ id: 42 }));
      }),
    );

    const { result, rerender } = renderHook(() => useUpdateAdminUserSetting(42), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ language: "fa" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });
});
