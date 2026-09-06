"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";
import type { AdminLogEntriesParams } from "../types.js";

/** v1.1.0. Wraps `GET /log-entries/` — Django's own `django.contrib.admin.models.LogEntry`;
 * every write made through Django Admin is auto-logged here already. Only ever populated (the
 * backend wires no route otherwise) when `django.contrib.admin` is installed. */
export function useAdminLogEntries(params?: AdminLogEntriesParams) {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.logEntries(params),
    queryFn: () => manager.listLogEntries(params),
  });
}
