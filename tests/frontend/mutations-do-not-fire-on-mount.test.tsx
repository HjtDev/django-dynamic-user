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
import { useUpdateMe } from "../../frontend/src/hooks/useUpdateMe.js";
import { useCreateAdminUser } from "../../frontend/src/hooks/useCreateAdminUser.js";
import { useDeleteAdminUser } from "../../frontend/src/hooks/useDeleteAdminUser.js";
import { useSetAdminUserPassword } from "../../frontend/src/hooks/useSetAdminUserPassword.js";
import { useCreateAdminProfile } from "../../frontend/src/hooks/useCreateAdminProfile.js";
import { useUpdateAdminProfileById } from "../../frontend/src/hooks/useUpdateAdminProfileById.js";
import { useDeleteAdminProfile } from "../../frontend/src/hooks/useDeleteAdminProfile.js";
import { useCreateAdminSetting } from "../../frontend/src/hooks/useCreateAdminSetting.js";
import { useUpdateAdminSettingById } from "../../frontend/src/hooks/useUpdateAdminSettingById.js";
import { useDeleteAdminSetting } from "../../frontend/src/hooks/useDeleteAdminSetting.js";
import { useCreateAdminDeletionRequest } from "../../frontend/src/hooks/useCreateAdminDeletionRequest.js";
import { useCancelAdminDeletionRequest } from "../../frontend/src/hooks/useCancelAdminDeletionRequest.js";
import { useDeleteAdminChangeLogEntry } from "../../frontend/src/hooks/useDeleteAdminChangeLogEntry.js";
import { useDeleteAdminLogEntry } from "../../frontend/src/hooks/useDeleteAdminLogEntry.js";
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
  makeUser,
} from "./fixtures.js";

/**
 * Every mutation hook this SDK ships — all twenty-three (v1.1.0 added fourteen to the original
 * nine), not a sample — must never fire on mount or a passive render (docs/APP-DESIGN.md §12's
 * frontend security checklist) — react-query's own
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

  // --- v1.1.0 additions ------------------------------------------------------------------

  it("useUpdateMe", async () => {
    let calls = 0;
    server.use(
      http.patch(`${TEST_BASE_URL}/api/v1/users/me/`, () => {
        calls += 1;
        return HttpResponse.json(makeUser({ name: "Renamed" }));
      }),
    );

    const { result, rerender } = renderHook(() => useUpdateMe(), {
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

  it("useCreateAdminUser", async () => {
    let calls = 0;
    server.use(
      http.post(`${TEST_BASE_URL}/api/v1/admin/users/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminUser(), { status: 201 });
      }),
    );

    const { result, rerender } = renderHook(() => useCreateAdminUser(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ username: "created", email: "created@example.com" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useDeleteAdminUser", async () => {
    let calls = 0;
    server.use(
      http.delete(`${TEST_BASE_URL}/api/v1/admin/users/42/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useDeleteAdminUser(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate(42);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useSetAdminUserPassword", async () => {
    let calls = 0;
    server.use(
      http.post(`${TEST_BASE_URL}/api/v1/admin/users/42/set-password/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useSetAdminUserPassword(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ id: 42, data: { password: "brandnewpassword123" } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useCreateAdminProfile", async () => {
    let calls = 0;
    server.use(
      http.post(`${TEST_BASE_URL}/api/v1/admin/users/profiles/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminProfile(), { status: 201 });
      }),
    );

    const { result, rerender } = renderHook(() => useCreateAdminProfile(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ user: 5 });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useUpdateAdminProfileById", async () => {
    let calls = 0;
    server.use(
      http.patch(`${TEST_BASE_URL}/api/v1/admin/users/profiles/3/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminProfile({ id: 3 }));
      }),
    );

    const { result, rerender } = renderHook(() => useUpdateAdminProfileById(3), {
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

  it("useDeleteAdminProfile", async () => {
    let calls = 0;
    server.use(
      http.delete(`${TEST_BASE_URL}/api/v1/admin/users/profiles/3/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useDeleteAdminProfile(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate(3);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useCreateAdminSetting", async () => {
    let calls = 0;
    server.use(
      http.post(`${TEST_BASE_URL}/api/v1/admin/users/settings/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminSetting(), { status: 201 });
      }),
    );

    const { result, rerender } = renderHook(() => useCreateAdminSetting(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ user: 5 });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useUpdateAdminSettingById", async () => {
    let calls = 0;
    server.use(
      http.patch(`${TEST_BASE_URL}/api/v1/admin/users/settings/3/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminSetting({ id: 3 }));
      }),
    );

    const { result, rerender } = renderHook(() => useUpdateAdminSettingById(3), {
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

  it("useDeleteAdminSetting", async () => {
    let calls = 0;
    server.use(
      http.delete(`${TEST_BASE_URL}/api/v1/admin/users/settings/3/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useDeleteAdminSetting(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate(3);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useCreateAdminDeletionRequest", async () => {
    let calls = 0;
    server.use(
      http.post(`${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/`, () => {
        calls += 1;
        return HttpResponse.json(makeAdminDeletionRequest(), { status: 201 });
      }),
    );

    const { result, rerender } = renderHook(() => useCreateAdminDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate({ user: 8, reason: "" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useCancelAdminDeletionRequest", async () => {
    let calls = 0;
    server.use(
      http.delete(`${TEST_BASE_URL}/api/v1/admin/users/deletion-requests/4/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useCancelAdminDeletionRequest(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate(4);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useDeleteAdminChangeLogEntry", async () => {
    let calls = 0;
    server.use(
      http.delete(`${TEST_BASE_URL}/api/v1/admin/users/change-log/6/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useDeleteAdminChangeLogEntry(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate(6);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });

  it("useDeleteAdminLogEntry", async () => {
    let calls = 0;
    server.use(
      http.delete(`${TEST_BASE_URL}/api/v1/admin/users/log-entries/11/`, () => {
        calls += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result, rerender } = renderHook(() => useDeleteAdminLogEntry(), {
      wrapper: createWrapper().Wrapper,
    });
    rerender();
    rerender();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(result.current.isIdle).toBe(true);
    expect(calls).toBe(0);

    result.current.mutate(11);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls).toBe(1);
  });
});
