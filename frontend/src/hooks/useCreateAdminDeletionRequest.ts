"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { CreateAdminDeletionRequestInput } from "../types.js";

/**
 * v1.1.0. Wraps `POST /deletion-requests/` — an admin filing a deletion request on a user's
 * behalf. Respects the same duplicate guard, `finalize_at` computation, and
 * `deletion_requested` signal every other creation path gets. `mutationFn` only ever runs from
 * an explicit `mutate()`/`mutateAsync()` call.
 */
export function useCreateAdminDeletionRequest() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateAdminDeletionRequestInput) => manager.createDeletionRequest(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.deletionRequests() });
    },
  });
}
