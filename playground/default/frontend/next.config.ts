import path from "node:path";
import type { NextConfig } from "next";

// Backend base URL for server-side rewrites — talks to the Django container directly
// (BACKEND_URL=http://backend-default:8000 in playground/docker-compose.yml), defaulting to
// localhost for `npm run dev` against a backend reachable on the host.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Next.js normalizes away trailing slashes with its OWN 308 redirect by default — proxied
  // through rewrites() below, that collides head-on with Django's CommonMiddleware
  // APPEND_SLASH, which redirects the other way (adds it back).
  skipTrailingSlashRedirect: true,
  // Turbopack's `root` is a hard compilation boundary. This repo's npm workspace root is the
  // REPO ROOT (root package.json: "workspaces": ["frontend", "playground/default/frontend",
  // "playground/subclassed/frontend"]) — not this directory's own — since frontend/ (the SDK
  // under test) is a sibling workspace member. Three levels up from
  // playground/default/frontend/ reaches the repo root.
  turbopack: {
    root: path.join(__dirname, "..", "..", ".."),
  },
  // Every route dynamic_user's admin API, self-service API, and Django's own auth views need is
  // proxied same-origin (localhost:3000) — every admin endpoint is IsDynamicUserAdmin-gated and
  // every self-service endpoint is IsAuthenticated, so the browser needs a real session cookie +
  // CSRF cookie, which only works cleanly same-origin with no CORS package and no
  // credentials:"include" plumbing.
  async rewrites() {
    // A single named param with an explicit `(.*)` regex, NOT a repeated `:path*` param — a
    // repeated param tokenizes into non-empty segments and silently drops a trailing slash,
    // which collides with Django's APPEND_SLASH into an infinite redirect loop on routes like
    // /admin/login/ (found live in ../../../cleanup_app/playground's own Phase 7 — see its
    // FINDINGS.md #2). `(.*)` captures the remainder as one raw string, trailing slash included.
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
