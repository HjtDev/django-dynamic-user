"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { UpdateAdminSettingInput } from "../types.js";

// Named distinctly from useAdminUserSetting(id) (the GET hook) — read/write split, matching
// every other resource in this SDK (docs/CONTRACT.md §10 item 10).
export function useUpdateAdminUserSetting(id: number) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateAdminSettingInput) => manager.updateUserSetting(id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserAdminKeys.userSetting(id) });
    },
  });
}
