"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/**
 * Wraps `POST /deletion-requests/{id}/finalize/` — bypasses the deletion grace period entirely
 * and is genuinely irreversible (a `hard_delete` mode deletes the user row). Superuser-only,
 * always, regardless of `ADMIN_REQUIRES_SUPERUSER`, enforced server-side. `id` travels with the
 * `mutate()` payload, matching `useReviewDeletionRequest()`'s shape (docs/CONTRACT.md §7:
 * `useFinalizeDeletionRequest()` takes no argument). `mutationFn` only ever runs from an
 * explicit `mutate()`/`mutateAsync()` call — see
 * tests/frontend/mutations-do-not-fire-on-mount.test.tsx.
 */
export function useFinalizeDeletionRequest() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => manager.finalizeDeletionRequest(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.deletionRequests() });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.deletionRequest(id) });
    },
  });
}
