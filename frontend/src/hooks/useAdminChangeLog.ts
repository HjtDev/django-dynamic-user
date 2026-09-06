"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { AdminChangeLogParams } from "../types.js";

/** v1.1.0. Wraps `GET /change-log/` — `HistoryMixin`'s own audit trail, previously readable
 * only through Django Admin's `ChangeLogEntryAdmin`. */
export function useAdminChangeLog(params?: AdminChangeLogParams) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.changeLog(params),
    queryFn: () => manager.listChangeLog(params),
  });
}
