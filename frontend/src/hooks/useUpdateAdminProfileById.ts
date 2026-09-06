"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { UpdateAdminProfileInput } from "../types.js";

/**
 * v1.1.0. Wraps `PATCH /profiles/{profileId}/` — keyed by the Profile row's own pk, not the
 * owning user's id. Named distinctly from `useUpdateAdminUserProfile(id)` (which PATCHes by
 * *user* id) to keep the two routes' identifiers from ever being confused at the call site.
 * `mutationFn` only ever runs from an explicit `mutate()`/`mutateAsync()` call.
 */
export function useUpdateAdminProfileById(profileId: number) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateAdminProfileInput) => manager.updateProfile(profileId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.profile(profileId) });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.profiles() });
    },
  });
}
