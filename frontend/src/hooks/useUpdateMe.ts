"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DynamicUserManager } from "../api/manager.js";
import { useDynamicUserConfig } from "../api/config.js";
import { dynamicUserKeys } from "./keys.js";
import type { UpdateMeInput } from "../types.js";

/**
 * v1.1.0. Wraps `PATCH /me/` — USER_SELF_EDITABLE_FIELDS minus USER_LOCKED_FIELDS, default just
 * `name`. `mutationFn` only ever runs from an explicit `mutate()`/`mutateAsync()` call.
 */
export function useUpdateMe() {
  const { client, basePath } = useDynamicUserConfig();
  const manager = useMemo(() => new DynamicUserManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateMeInput) => manager.updateMe(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: dynamicUserKeys.me() });
    },
  });
}
