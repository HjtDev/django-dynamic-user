"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { UpdateAdminUserInput } from "../types.js";

/**
 * Wraps `PATCH /{id}/`. A privileged-field write (`is_active`/`is_staff`/`is_superuser`/
 * `groups`/`user_permissions`) is rejected server-side by `CanEscalatePrivilege` unless the
 * caller is an actual superuser — this hook makes no client-side attempt to pre-filter the body.
 * `mutationFn` only ever runs from an explicit `mutate()`/`mutateAsync()` call — see
 * tests/frontend/mutations-do-not-fire-on-mount.test.tsx.
 */
export function useUpdateAdminUser(id: number) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateAdminUserInput) => manager.updateUser(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.user(id) });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.users() });
    },
  });
}
