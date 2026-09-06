"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { CreateAdminProfileInput } from "../types.js";

/**
 * v1.1.0. Wraps `POST /profiles/` — `user` is writable in the input (unlike
 * `useUpdateAdminProfileById`'s shape), since naming which user this new row belongs to is the
 * entire point of a create call. `mutationFn` only ever runs from an explicit
 * `mutate()`/`mutateAsync()` call.
 */
export function useCreateAdminProfile() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateAdminProfileInput) => manager.createProfile(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.profiles() });
    },
  });
}
