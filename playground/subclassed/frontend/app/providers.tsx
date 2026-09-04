"use client";

import { useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ApiClientProvider } from "@hjtdev/appkit";
import { makeQueryClient } from "@/lib/query-client";
import { apiClient } from "@/lib/api-client";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {/* Both basePath keys — this app's whole SDK needs both, not just "dynamic_user":
          docs/INTEGRATION-GUIDE.md §2 step 11's own warning about a typo'd/missing key silently
          falling back instead of failing to build. */}
      <ApiClientProvider
        client={apiClient}
        basePaths={{
          dynamic_user: "/api/v1/users",
          dynamic_user_admin: "/api/v1/admin/users",
        }}
      >
        {children}
      </ApiClientProvider>
    </QueryClientProvider>
  );
}
