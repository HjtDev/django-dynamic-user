"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/**
 * v1.1.0. Wraps `DELETE /deletion-requests/{id}/` — a PENDING or APPROVED request only; 409 if
 * already REJECTED/FINALIZED. `mutationFn` only ever runs from an explicit
 * `mutate()`/`mutateAsync()` call.
 */
export function useCancelAdminDeletionRequest() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => manager.cancelDeletionRequest(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.deletionRequests() });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.deletionRequest(id) });
    },
  });
}
