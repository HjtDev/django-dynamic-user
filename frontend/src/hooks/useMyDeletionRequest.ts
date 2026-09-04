"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { DynamicUserManager } from "../api/manager.js";
import { useDynamicUserConfig } from "../api/config.js";
import { dynamicUserKeys } from "./keys.js";

export function useMyDeletionRequest() {
  const { client, basePath } = useDynamicUserConfig();
  const manager = useMemo(() => new DynamicUserManager(client, basePath), [client, basePath]);

  return useQuery({
    queryKey: dynamicUserKeys.myDeletionRequest(),
    queryFn: () => manager.getMyDeletionRequest(),
  });
}
