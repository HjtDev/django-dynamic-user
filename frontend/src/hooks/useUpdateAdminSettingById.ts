"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { UpdateAdminSettingInput } from "../types.js";

/**
 * v1.1.0. Wraps `PATCH /settings/{settingId}/` — keyed by the Setting row's own pk, not the
 * owning user's id. Named distinctly from `useUpdateAdminUserSetting(id)` (which PATCHes by
 * *user* id), same reasoning as `useUpdateAdminProfileById`. `mutationFn` only ever runs from an
 * explicit `mutate()`/`mutateAsync()` call.
 */
export function useUpdateAdminSettingById(settingId: number) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateAdminSettingInput) => manager.updateSetting(settingId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.setting(settingId) });
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.settings() });
    },
  });
}
