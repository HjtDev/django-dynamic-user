"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/**
 * v1.1.0. Wraps `DELETE /{id}/` — superuser-only, always, regardless of
 * `ADMIN_REQUIRES_SUPERUSER`, enforced server-side. Hard-deletes the user outright, bypassing
 * the account-deletion review flow entirely. `mutationFn` only ever runs from an explicit
 * `mutate()`/`mutateAsync()` call — this is irreversible.
 */
export function useDeleteAdminUser() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => manager.deleteUser(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.user(id) });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.users() });
    },
  });
}
