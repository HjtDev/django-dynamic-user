"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/** v1.1.0. Wraps `GET /profiles/{profileId}/` — keyed by the Profile row's own pk, not the
 * owning user's id (that's `useAdminUserProfile(id)`, which this complements, not replaces). */
export function useAdminProfile(profileId: number) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.profile(profileId),
    queryFn: () => manager.getProfile(profileId),
    enabled: Number.isFinite(profileId),
  });
}
