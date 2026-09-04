import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAdminUsers } from "../../frontend/src/hooks/useAdminUsers.js";
import { useUpdateAdminUser } from "../../frontend/src/hooks/useUpdateAdminUser.js";
import { server } from "./setup.js";
import { createWrapper, TEST_BASE_URL } from "./helpers.js";
import { makeAdminUser, makePaginatedAdminUserList } from "./fixtures.js";

const USERS_URL = `${TEST_BASE_URL}/api/v1/admin/users/`;
const USER_URL = `${TEST_BASE_URL}/api/v1/admin/users/1/`;

/**
 * Regression for the dynamicUserAdminKeys.users(params) key-shape fix (docs/CONTRACT.md §10):
 * dropping the `params` slot entirely on a no-argument call, rather than emitting
 * [..., "users", undefined], is what lets `invalidateQueries({ queryKey: users() })` actually
 * match a *filtered* live query's key ([..., "users", { page: 2 }]). If keys.ts regresses to the
 * flat `[...all, "users", params]` form the CONTRACT §7 snippet originally showed, this test
 * fails: the filtered query below would never refetch after useUpdateAdminUser's mutation.
 */
describe("dynamicUserAdminKeys.users() invalidation reaches a filtered query", () => {
  it("refetches a page-filtered useAdminUsers query after useUpdateAdminUser succeeds", async () => {
    let usersCallCount = 0;
    server.use(
      http.get(USERS_URL, () => {
        usersCallCount += 1;
        return HttpResponse.json(makePaginatedAdminUserList());
      }),
      http.patch(USER_URL, () => HttpResponse.json(makeAdminUser({ id: 1, name: "Renamed" }))),
    );

    const { Wrapper } = createWrapper();

    const list = renderHook(() => useAdminUsers({ page: 2 }), { wrapper: Wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));
    expect(usersCallCount).toBe(1);

    const mutation = renderHook(() => useUpdateAdminUser(1), { wrapper: Wrapper });
    mutation.result.current.mutate({ name: "Renamed" });
    await waitFor(() => expect(mutation.result.current.isSuccess).toBe(true));

    // The invalidation is what triggers the refetch; wait for the count to move rather than
    // asserting immediately, since react-query's refetch happens asynchronously after onSuccess.
    await waitFor(() => expect(usersCallCount).toBe(2));
  });
});
