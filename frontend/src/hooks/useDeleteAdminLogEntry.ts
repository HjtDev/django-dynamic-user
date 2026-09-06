"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/**
 * v1.1.0. Wraps `DELETE /log-entries/{id}/` — superuser-only, always, enforced server-side,
 * same reasoning as `useDeleteAdminChangeLogEntry`. `mutationFn` only ever runs from an explicit
 * `mutate()`/`mutateAsync()` call.
 */
export function useDeleteAdminLogEntry() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => manager.deleteLogEntry(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.logEntries() });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.logEntry(id) });
    },
  });
}
