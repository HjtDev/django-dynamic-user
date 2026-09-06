"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/**
 * v1.1.0. Wraps `DELETE /profiles/{profileId}/`. `mutationFn` only ever runs from an explicit
 * `mutate()`/`mutateAsync()` call.
 */
export function useDeleteAdminProfile() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (profileId: number) => manager.deleteProfile(profileId),
    onSuccess: (_data, profileId) => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.profile(profileId) });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.profiles() });
    },
  });
}
