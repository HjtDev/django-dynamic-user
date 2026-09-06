"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/** v1.1.0. Wraps `GET /deletion-requests/{id}/` — backs the previously-unpopulated
 * `dynamicUserAdminKeys.deletionRequest(id)` key. */
export function useAdminDeletionRequest(id: number) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.deletionRequest(id),
    queryFn: () => manager.getDeletionRequest(id),
    enabled: Number.isFinite(id),
  });
}
