"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/** v1.1.0. Wraps `GET /settings/{settingId}/` — keyed by the Setting row's own pk, not the
 * owning user's id. */
export function useAdminSetting(settingId: number) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.setting(settingId),
    queryFn: () => manager.getSetting(settingId),
    enabled: Number.isFinite(settingId),
  });
}
