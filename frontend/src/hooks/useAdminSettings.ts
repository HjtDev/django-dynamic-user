"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { AdminSettingsParams } from "../types.js";

/** v1.1.0. Wraps `GET /settings/` (admin collection). */
export function useAdminSettings(params?: AdminSettingsParams) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.settings(params),
    queryFn: () => manager.listSettings(params),
  });
}
