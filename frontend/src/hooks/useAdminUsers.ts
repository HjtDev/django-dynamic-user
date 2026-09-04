"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { AdminUsersParams } from "../types.js";

export function useAdminUsers(params?: AdminUsersParams) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.users(params),
    queryFn: () => manager.listUsers(params),
  });
}
