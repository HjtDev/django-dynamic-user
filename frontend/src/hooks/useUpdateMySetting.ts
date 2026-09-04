"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserManager } from "../api/manager.js";
import { useDynamicUserConfig } from "../api/config.js";
import { dynamicUserKeys } from "./keys.js";
import type { UpdateMySettingInput } from "../types.js";

export function useUpdateMySetting() {
  const { client, basePath } = useDynamicUserConfig();
  const manager = useMemo(() => new DynamicUserManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateMySettingInput) => manager.updateMySetting(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserKeys.mySetting() });
    },
  });
}
