# @hjtdev/django-dynamic-user

Typed React hooks over `django-dynamic-user`'s two API surfaces — self-service
(`/api/v1/users`) and admin (`/api/v1/admin/users`) — generated from the backend's own
OpenAPI schema.

- **npm package:** `@hjtdev/django-dynamic-user`. **PyPI distribution:** `django-dynamic-user`.
- Two `basePaths` entries are required on `@hjtdev/appkit`'s `ApiClientProvider`: `dynamic_user`
  (self-service) and `dynamic_user_admin` (admin). A host wiring only one is a documented failure
  mode — see the root `README.md`'s "Usage — frontend" section once it exists (Phase 9).
- This app does not do authentication — no registration, login, JWT, or password reset.

This is a stub, replaced by Phase 9's real README (root `README.md`, then copied here verbatim by
`make sync-readmes`). See `docs/CONTRACT.md` §7 for the frozen hook contract in the meantime.
