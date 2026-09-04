import path from "node:path";
import type { NextConfig } from "next";

// Backend base URL for server-side rewrites — talks to the Django container directly
// (BACKEND_URL=http://backend-subclassed:8000 in playground/docker-compose.yml), defaulting to
// localhost:8001 for `npm run dev` against a backend reachable on the host (:8000 is the
// DEFAULT host — the two must never collide).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  // Same repo-root pin as ../../default/frontend/next.config.ts — see that file's own comment.
  turbopack: {
    root: path.join(__dirname, "..", "..", ".."),
  },
  async rewrites() {
    // `:path(.*)`, never a repeated `:path*` — see ../../default/frontend/next.config.ts's own
    // comment for the trailing-slash/APPEND_SLASH redirect-loop this avoids.
    return [
      { source: "/api/:path(.*)", destination: `${BACKEND_URL}/api/:path` },
      { source: "/admin/:path(.*)", destination: `${BACKEND_URL}/admin/:path` },
      { source: "/accounts/:path(.*)", destination: `${BACKEND_URL}/accounts/:path` },
      { source: "/static/:path(.*)", destination: `${BACKEND_URL}/static/:path` },
      { source: "/media/:path(.*)", destination: `${BACKEND_URL}/media/:path` },
    ];
  },
};

export default nextConfig;
