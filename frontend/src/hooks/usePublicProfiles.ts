"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserManager } from "../api/manager.js";
import { useDynamicUserConfig } from "../api/config.js";
import { dynamicUserKeys } from "./keys.js";
import type { PublicProfilesParams } from "../types.js";

export function usePublicProfiles(params?: PublicProfilesParams) {
  const { client, basePath } = useDynamicUserConfig();
  const manager = useMemo(() => new DynamicUserManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserKeys.publicProfiles(params),
    queryFn: () => manager.listPublicProfiles(params),
  });
}
