# django-dynamic-user

Swappable `User`/`Profile`/`Setting` data layer for a host Django project, as an installable app
package.

- **Importable module:** `dynamic_user`.
- **PyPI distribution:** `django-dynamic-user`. **npm package:** `@hjtdev/django-dynamic-user`.
- This app does not do authentication — no registration, login, JWT, or password reset. It is the
  data layer a separate `auth-app` package reaches through `get_user_model()`, the same
  indirection `django.contrib.auth`'s own views use.

This is a stub, replaced by Phase 9's real README (root `README.md`, then copied here verbatim by
`make sync-readmes`). See `docs/CONTRACT.md` for the frozen public contract in the meantime.
