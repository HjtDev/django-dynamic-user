"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserManager } from "../api/manager.js";
import { useDynamicUserConfig } from "../api/config.js";
import { dynamicUserKeys } from "./keys.js";

/**
 * Wraps `DELETE /me/deletion-request/`. `mutationFn` only ever runs from an explicit `mutate()`/
 * `mutateAsync()` call — see tests/frontend/mutations-do-not-fire-on-mount.test.tsx.
 */
export function useCancelDeletionRequest() {
  const { client, basePath } = useDynamicUserConfig();
  const manager = useMemo(() => new DynamicUserManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => manager.cancelDeletionRequest(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserKeys.myDeletionRequest() });
    },
  });
}
