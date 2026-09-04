"use client";

// Internal — never exported from src/index.ts. Every real app SDK's api/config.ts follows this
// exact shape: a thin call to appkit's useApiClient(key, defaultBasePath), never anything
// host-specific. This app registers TWO surfaces, each with its own namespace key and default
// basePath (docs/CONTRACT.md §0 / CLAUDE.md's namespacing table) — the first app in the
// ecosystem that needs two, so a host must add both entries to its own `basePaths` map, not one.
import { useApiClient } from "@hjtdev/appkit";

export const useDynamicUserConfig = () => useApiClient("dynamic_user", "/api/v1/users");

export const useDynamicUserAdminConfig = () =>
  useApiClient("dynamic_user_admin", "/api/v1/admin/users");
