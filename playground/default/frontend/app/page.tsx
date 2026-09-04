// Provider-dependent hooks live in a separate "use client" component (MeClient) — this server
// wrapper only exists to export `dynamic = "force-dynamic"`. Placed directly in a "use client"
// file the directive is silently ignored, and `next build`'s static-generation pass then
// prerenders MeClient in a worker with no provider mounted, failing with "No QueryClient set,
// use QueryClientProvider to set one" — found live in
// ../../../cleanup_app/playground's own Phase 7 (its README/APP-DESIGN.md §11.2 note).
export const dynamic = "force-dynamic";

import { MeClient } from "./MeClient";

export default function Page() {
  return <MeClient />;
}
