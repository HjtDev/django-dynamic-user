"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserManager } from "../api/manager.js";
import { useDynamicUserConfig } from "../api/config.js";
import { dynamicUserKeys } from "./keys.js";
import type { UpdateMyProfileInput } from "../types.js";

export function useUpdateMyProfile() {
  const { client, basePath } = useDynamicUserConfig();
  const manager = useMemo(() => new DynamicUserManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateMyProfileInput) => manager.updateMyProfile(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserKeys.myProfile() });
    },
  });
}
