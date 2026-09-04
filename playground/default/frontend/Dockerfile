# Built with the REPO ROOT as context (playground/docker-compose.yml: `context: ..`), preserving
# the on-disk layout — /app/frontend (this app's own SDK, a workspace member) and
# /app/playground/default/frontend (also a workspace member) — so the repo-root npm WORKSPACE
# resolves identically in and out of Docker. One hoisted node_modules dedupes
# react/@tanstack/react-query/@hjtdev/appkit between the SDK and this host.
#
# Full source copied before the one root-level `npm install`, not a package.json-only layer —
# frontend/package.json's own `prepare` script (`tsc -p tsconfig.build.json`) runs automatically
# as part of a workspace install and needs tsconfig.build.json and src/ already present. A
# package.json-only first layer fails the build outright with `error TS5058: The specified path
# does not exist: 'tsconfig.build.json'` — found live in ../../../cleanup_app/playground's own
# Phase 7 (its FINDINGS.md #8).
FROM node:22-alpine
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json /app/
COPY frontend/ /app/frontend/
COPY playground/default/frontend/ /app/playground/default/frontend/
COPY playground/subclassed/frontend/package.json /app/playground/subclassed/frontend/package.json
RUN npm install

WORKDIR /app/playground/default/frontend

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
