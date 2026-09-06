"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { CreateAdminUserInput } from "../types.js";

/**
 * v1.1.0. Wraps `POST /`. A privileged-field write is rejected server-side by
 * `CanEscalatePrivilege` unless the caller is an actual superuser — same rule as
 * `useUpdateAdminUser`. `mutationFn` only ever runs from an explicit `mutate()`/`mutateAsync()`
 * call.
 */
export function useCreateAdminUser() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateAdminUserInput) => manager.createUser(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.users() });
    },
  });
}
