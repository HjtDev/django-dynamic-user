"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { AdminProfilesParams } from "../types.js";

/** v1.1.0. Wraps `GET /profiles/` (admin collection) — not restricted to `is_public=True`,
 * unlike the self-service `usePublicProfiles`. */
export function useAdminProfiles(params?: AdminProfilesParams) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.profiles(params),
    queryFn: () => manager.listProfiles(params),
  });
}
