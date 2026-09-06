"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import { dynamicUserAdminKeys } from "./keys.js";

/** v1.1.0. Wraps `GET /groups/` — read-only, populates the picker behind `useUpdateAdminUser`'s
 * `groups` field. Full Group CRUD stays `django.contrib.auth`'s own admin surface. */
export function useAdminGroups() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserAdminKeys.groups(),
    queryFn: () => manager.listGroups(),
  });
}
