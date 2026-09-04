"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserManager } from "../api/manager.js";
import { useDynamicUserConfig } from "../api/config.js";
import { dynamicUserKeys } from "./keys.js";
import type { RequestDeletionInput } from "../types.js";

/**
 * Wraps `POST /me/deletion-request/` — an irreversible-in-effect action (starts the account
 * deletion grace period). `mutationFn` only ever runs from an explicit `mutate()`/
 * `mutateAsync()` call; react-query never fires it on mount or a passive render — see
 * tests/frontend/mutations-do-not-fire-on-mount.test.tsx.
 */
export function useRequestDeletion() {
  const { client, basePath } = useDynamicUserConfig();
  const manager = useMemo(() => new DynamicUserManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body?: RequestDeletionInput) => manager.requestDeletion(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserKeys.myDeletionRequest() });
    },
  });
}
