"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

export function useAdminUserSetting(id: number) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.userSetting(id),
    queryFn: () => manager.getUserSetting(id),
    enabled: Number.isFinite(id),
  });
}
