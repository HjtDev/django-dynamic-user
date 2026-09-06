"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/**
 * v1.1.0. Wraps `DELETE /change-log/{id}/` — superuser-only, always, enforced server-side: an
 * audit row deleted by anything less is exactly the tampering an audit trail exists to make
 * visible. `mutationFn` only ever runs from an explicit `mutate()`/`mutateAsync()` call.
 */
export function useDeleteAdminChangeLogEntry() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => manager.deleteChangeLogEntry(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.changeLog() });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.changeLogEntry(id) });
    },
  });
}
