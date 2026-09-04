"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

export interface ReviewDeletionRequestVariables {
  id: number;
  approved: boolean;
}

/**
 * Wraps `POST /deletion-requests/{id}/review/`. Unlike `useUpdateAdminUser`/
 * `useUpdateAdminUserProfile`/`useUpdateAdminUserSetting`, `id` isn't bound at the hook call —
 * a queue UI reviewing many requests shouldn't need a fresh hook instance per row, so `id`
 * travels with the `mutate()` payload instead (docs/CONTRACT.md §7: `useReviewDeletionRequest()`
 * takes no argument). `mutationFn` only ever runs from an explicit `mutate()`/`mutateAsync()`
 * call — an irreversible-in-effect action (moves a request to APPROVED/REJECTED); see
 * tests/frontend/mutations-do-not-fire-on-mount.test.tsx.
 */
export function useReviewDeletionRequest() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, approved }: ReviewDeletionRequestVariables) =>
      manager.reviewDeletionRequest(id, approved),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.deletionRequests() });
      void queryClient.invalidateQueries({
        queryKey: dynamicUserAdminKeys.deletionRequest(variables.id),
      });
    },
  });
}
