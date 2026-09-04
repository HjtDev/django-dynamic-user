"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserManager } from "../api/manager.js";
import { useDynamicUserConfig } from "../api/config.js";
import { dynamicUserKeys } from "./keys.js";

// `id` is the target USER's id, not the Profile row's own pk (docs/CONTRACT.md §10 item 6).
export function usePublicProfile(id: number) {
  const { client, basePath } = useDynamicUserConfig();
  const manager = useMemo(() => new DynamicUserManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserKeys.publicProfile(id),
    queryFn: () => manager.getPublicProfile(id),
    enabled: Number.isFinite(id),
  });
}
