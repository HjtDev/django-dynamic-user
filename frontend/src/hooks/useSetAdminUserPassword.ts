"use client";

import { useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { DynamicUserAdminManager } from "../api/manager.js";
import { useDynamicUserAdminConfig } from "../api/config.js";
import type { SetAdminUserPasswordInput } from "../types.js";

export interface SetAdminUserPasswordVariables {
  id: number;
  data: SetAdminUserPasswordInput;
}

/**
 * v1.1.0. Wraps `POST /{id}/set-password/` — superuser-only, always, enforced server-side.
 * Runs `AUTH_PASSWORD_VALIDATORS` and sends `user_password_set`. No cache to invalidate —
 * `password` is never part of any read shape this SDK exposes. `mutationFn` only ever runs from
 * an explicit `mutate()`/`mutateAsync()` call.
 */
export function useSetAdminUserPassword() {
  const { client, basePath } = useDynamicUserAdminConfig();
  const manager = useMemo(() => new DynamicUserAdminManager(client, basePath), [client, basePath]);

  return useMutation({
    mutationFn: ({ id, data }: SetAdminUserPasswordVariables) => manager.setUserPassword(id, data),
  });
}
