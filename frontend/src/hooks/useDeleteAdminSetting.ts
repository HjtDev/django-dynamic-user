"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/**
 * v1.1.0. Wraps `DELETE /settings/{settingId}/`. `mutationFn` only ever runs from an explicit
 * `mutate()`/`mutateAsync()` call.
 */
export function useDeleteAdminSetting() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (settingId: number) => manager.deleteSetting(settingId),
    onSuccess: (_data, settingId) => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.setting(settingId) });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.settings() });
    },
  });
}
