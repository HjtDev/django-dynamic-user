# graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

# CLAUDE.md — django-dynamic-user (app package #3)

A standalone, versioned, dual-package Django + React app package that **is** a host project's
user data layer: swappable `User`/`Profile`/`Setting` models (installed as-is, or subclassed by a
host for project-specific fields), self-service and admin DRF surfaces, a Jazzmin admin, an
opt-out account-deletion review flow, a small mixin library (`Avatar`, `Timestamp`, `History`,
`SoftDelete`, `Verification`, `LastSeen`, `Metadata`), and frontend hooks for both surfaces. It
depends on `appkit` (app package #1) for caching, pagination, permissions, error envelope, and
`HttpClient`/provider, exactly like every other app in this ecosystem.

**This app does not do authentication.** No registration, login, JWT, or password reset — that is
a separate `auth-app` package's job, reaching this one only through `get_user_model()`, the same
indirection `django.contrib.auth`'s own views use.

**Read `docs/APP-DESIGN.md` in full before making changes.** For the actual build order, use
**`docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`** — it is this project's own pre-customized
instance of `docs/CLAUDE-CODE-GUIDE-APP.md`, with every phase prompt, model, endpoint, setting,
and hook already decided so a phase session is paste-and-go instead of a re-derive-the-prompt
session. Once `docs/CONTRACT.md` exists (Phase 0), read that too — it's the frozen contract this
file's summary reflects. This file is the fast reference; the guide is the map.

**Shared docs live in `HjtDev/ecosystem-docs`, not here.** `docs/APP-DESIGN.md`,
`docs/BASE-DESIGN.md`, `docs/INTEGRATION-GUIDE.md`, `docs/CLAUDE-CODE-GUIDE-APP.md`, and
`docs/CLAUDE-CODE-GUIDE-BASE.md` are symlinks into a sibling `../ecosystem-docs` checkout
(`make docs-link`) — the same five files, unchanged, shared with `appkit` and `cleanup_app`.
**Edit them there, never here** — a local edit to the symlink target changes the file in every
project that links it, which is the point, but only if the edit actually lands in
`ecosystem-docs` and gets committed/pushed from that repo. `docs/CONTRACT.md`,
`docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`, and `docs/SECURITY-CHECKLIST.md` are this
project's own and stay real files here.

## The rules that define this package

1. **Every model reference is indirect, always.** `settings.AUTH_USER_MODEL` for the user;
   `dynamic_user.resolution.get_profile_model()` / `get_setting_model()` for the other two —
   mirroring `django.contrib.auth.get_user_model()`. **Never** `from dynamic_user.models import
   User/Profile/Setting` anywhere in this package's own code, including its own `admin.py` and
   `services.py`. The entire point of this app is that a host can subclass any of the three
   models; one concrete import breaks that for every host that does.
2. **A settings change must never produce a migration diff.** Field allowlists, validator lists,
   and anything else in `DYNAMIC_USER` are resolved at call time by a serializer factory / a
   validator wrapper — never baked into a model's class attributes or `Meta`. The one sanctioned
   exception, forced by Django itself, is `USERNAME_FIELD`/`REQUIRED_FIELDS` on the abstract user
   base — changing those genuinely is a one-time, pre-migrate host decision, not a runtime
   setting.
3. **This app holds credentials and PII.** No serializer, on either surface, ever emits `password`
   or a hash. No code path reachable by a non-superuser — including the requesting user's own
   self-service views — may write `is_staff`, `is_superuser`, or `is_active` on any user. A public
   profile response exposes exactly the settings-declared allowlist intersected with the resolved
   model's real fields, never `"__all__"`.
4. **Two declared dependencies, and nothing else, beyond what ships with Django.** `appkit` (cache,
   pagination, permissions, error envelope, `HttpClient`/provider) is a real, versioned
   dependency; `django.contrib.contenttypes` (used only by the `History` mixin) ships with Django
   itself and isn't a §6 boundary concern. No other app package is ever imported, in any form.
5. **Two admin postures, one switch.** `appkit.permissions.IsAppAdmin` (`is_staff`) gates the admin
   surface by default; `DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]=True` tightens every admin gate
   to `is_superuser`. Independent of that switch, and never relaxed by it: only an actual
   superuser may write `is_staff`/`is_superuser`/`is_active` on anyone.
6. **Wide dependency ranges, never exact pins**, on `django`, `djangorestframework`,
   `drf-spectacular`, and `appkit` — anything a host also depends on directly.
7. **Both halves release under one tag** — `pyproject.toml`, `package.json`, `CHANGELOG.md` agree;
   CI fails the build otherwise.
8. **Namespace everything landing in a shared namespace** — settings dict `DYNAMIC_USER`, two
   top-level swappable-model settings (`DYNAMIC_USER_PROFILE_MODEL`,
   `DYNAMIC_USER_SETTING_MODEL`), throttle prefix `dynamic_user_` (admin views additionally prefix
   `dynamic_user_admin_`), cache namespace `dynamic_user`, **two** frontend basePath keys
   (`dynamic_user` → `/api/v1/users`, `dynamic_user_admin` → `/api/v1/admin/users`), Celery task
   names `dynamic_user.tasks.*`. `APP-DESIGN.md` §1.2.

## Scope boundary

| In | Out |
|---|---|
| `User`/`Profile`/`Setting` — abstract bases + swappable concrete defaults, mixin library | Registration, login, JWT, password reset, session/token management — a separate `auth-app`'s job |
| Self-service views: see own info, edit own profile/setting, browse others' public profiles | Editing anyone else's data from the self-service surface — there is no such endpoint |
| Admin API + Jazzmin admin: full read/write over every user, gated by `IsAppAdmin`/superuser | Privilege escalation from anything less than an actual superuser, ever |
| Opt-out account-deletion request, review, and finalize flow (task or command driven) | Sending any notification about it — that's a host's/notification-app's job, reached via this app's signals |
| A settings-driven serializer factory so a host's subclassed model needs zero view-layer changes | A per-host serializer subclass as the sanctioned customization path — allowlists are |
| Region-specific validator hooks (`PHONE_VALIDATORS`, `NAME_VALIDATORS`) | Any opinionated phone/name format shipped by default — the hook is the feature, not a validator |

## Dependency ranges & pinned versions

| Decision | Value |
|---|---|
| Python | `requires-python = ">=3.13"` (range); `.python-version` pins `3.14` locally |
| Django / DRF | `>=5.2,<7.0` / `>=3.15,<4.0` |
| `appkit` | `hjtdev-appkit>=2.0,<3.0` |
| Celery (optional `celery` extra) | `celery[redis]>=5.4,<6.0`, `django-celery-beat>=2.7,<3.0` |
| Avatar (optional `avatar` extra) | `hjtdev-appkit[images]>=2.0,<3.0` — confirm the exact extra name against appkit's own `pyproject.toml`/README before relying on it, don't assume |
| React / `@tanstack/react-query` (peer deps) | `>=18` / `>=5` |
| `@hjtdev/appkit` (peer dep) | matching appkit's own published major |
| Vitest | 4.x |
| Coverage gate | **85%** — the standard app-package bar |

## Commands

Tests run on Postgres, not SQLite (`docs/APP-DESIGN.md` §7.5), against **two** settings modules —
`tests.backend.settings` (default models) and `tests.backend.settings_swapped` (a host-style
subclass of all three) — every phase from Phase 2 onward. `make check` (repo root) is the local
equivalent of the raw commands below — it brings up `docker-compose.test.yml`'s ephemeral Postgres
itself, so a fresh clone needs nothing pre-installed beyond Docker and `uv`.

```bash
cd backend && uv sync                              # core only
uv sync --extra celery                              # prove the optional extra resolves
uv sync --extra avatar                              # prove the optional extra resolves
uv run pytest                                        # gate: authoritative, >=85% coverage, default settings
DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped uv run pytest -k swapped  # the swap-model gate
uv run --exact pytest -m "not requires_extra" --no-cov   # bare-install check, no extras
uv run ruff check --fix . ../tests && uv run ruff format . ../tests
uv run mypy src
uv build

cd frontend && npm ci
npm run test                      # Vitest + MSW — authoritative gate for the TS half
npx tsc --noEmit && npm run lint

# Verify against real hosts before tagging — playground/default and playground/subclassed
cd playground/default/backend && uv sync
docker compose -f playground/docker-compose.yml up
```

CI: `.github/workflows/ci.yml` here is a ~10-line caller only, per `docs/APP-DESIGN.md` §10.2,
using the org-level reusable workflow at `HjtDev/.github`'s `app-package-ci.yml` — not recreated
locally, plus this repo's own `publish-pypi` job (§10.2 explains why that one can't live in the
shared workflow).

## Semver triggers — MAJOR bumps even when the diff is small

- Removing/renaming a signal (`profile_created`, `setting_created`, `deletion_requested`,
  `deletion_reviewed`, `deletion_finalized`, `profile_updated`), a `services.py` method signature,
  an exported hook, or a field a host might query on `User`/`Profile`/`Setting`/
  `AccountDeletionRequest`.
- Renaming a `DYNAMIC_USER` settings key, or either of the two top-level swappable-model settings
  (`DYNAMIC_USER_PROFILE_MODEL`, `DYNAMIC_USER_SETTING_MODEL`).
- Narrowing a default field allowlist (`*_EDITABLE_FIELDS`, `*_PUBLIC_FIELDS`, `USER_READ_FIELDS`)
  — a host relying on the default silently loses access to a field it could read/write before.
- Changing `build_serializer()`'s signature, or what `resolution.get_profile_model()`/
  `get_setting_model()` return or raise on misconfiguration.
- Weakening a default safety rail — loosening the privilege-escalation guard, changing
  `ADMIN_REQUIRES_SUPERUSER`'s default, shortening `DELETION_GRACE_PERIOD_DAYS`'s default, or
  changing `DELETION_MODE`'s default — treat as breaking even if it's "just a default," since a
  host that never overrode it inherits the new behavior silently.
- Renaming the published distribution name (`django-dynamic-user` / `@hjtdev/django-dynamic-user`).

Every one needs a **Host action:** line in `CHANGELOG.md`.

## Working agreement (delete after v1.0.0 ships)

- One phase at a time, per `docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`. Don't create files
  outside the current phase's scope.
- Re-read the relevant `docs/APP-DESIGN.md` section, and this app's own guide section, before
  writing files it specifies.
- After each phase, run its verification command **against both settings modules** where the
  phase touches business logic, and paste the real output. Never report success you haven't
  observed.
- If the spec is ambiguous or looks wrong, ask. Don't guess and proceed.
- This package must work in ANY host project, with its default models OR a fully subclassed set.
  **Whenever you're about to write `from dynamic_user.models import User` (or `Profile`/
  `Setting`) anywhere in this package's own code**, stop — that's the constraint this whole
  design exists for. Use `settings.AUTH_USER_MODEL` or `resolution.py` instead.
- Whenever you're about to write code that reads or writes `is_staff`/`is_superuser`/`is_active`,
  stop and confirm a non-superuser request can never reach it. This is the one constraint that
  matters more than the boundary rule above.

## Definition of done

- `docs/CONTRACT.md` and the code agree; `README.md` and the code agree.
- `backend/README.md` and `frontend/README.md` are current copies of `README.md`
  (`readme-contract` CI job green).
- Both halves at the same version, in all three places; CI's lockstep job green.
- `uv run pytest` (against both settings modules) and `npm run test` green, over 85% coverage.
- `ruff`, `mypy`, `tsc --noEmit`, `eslint` all clean.
- Zero imports of another app package; zero concrete `User`/`Profile`/`Setting` imports anywhere
  in this package's own code; `appkit` and `django.contrib.contenttypes` are the only exceptions.
- Every emitted signal has a test asserting its exact documented payload.
- Every endpoint has a non-permitted-user-gets-403(-or-404) test that actually fails when the
  relevant permission check is removed.
- The privilege-escalation guard is proven, not assumed, by an actual attempt against it.
- Playground verified on **both** hosts: default models and a fully subclassed set, the latter's
  extra field round-tripping over real HTTP with zero package-level code changes.
- Security checklists (`APP-DESIGN.md` §9 and §12) walked with evidence, not assumed.
- Installed into a fresh `base-scaffold` clone twice (default, then subclassed) using only the
  README.
- Tagged `v1.0.0`; PyPI and npm entries both show a real, non-empty description — checked
  directly against the registry, not assumed from green CI.

## Git protocol

- Never stage or commit unless explicitly asked. Every diff gets reviewed before it lands.
- Never `git push`, `git reset --hard`, `git checkout <branch>`, force-push, or amend an existing
  commit. Ever. Ask instead.
- When a phase or task is done, don't commit — summarise what changed and the verification output
  that passed, propose a commit message in the format below (fenced, copy-pasteable), then stop
  and wait for review.
- If something needs reverting, say so and let the reviewer do it.

### Commit message format

```
semantic(<scope>): <short_commit_message>

- Add <what was added>
- Remove <what was removed>
- Update <what was changed>
```

Rules for it:
- `semantic` is one of: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `build`, `ci`, `perf`,
  `style`. Use `!` after the scope for a breaking change: `feat(services)!:`.
- `<scope>`: lowercase, one word — `backend`, `frontend`, `api`, `hooks`, `ci`, `deps`,
  `playground`, `docs`, `admin`. Narrowest scope that covers the change.
- `<short_commit_message>`: imperative mood, lowercase, no trailing period, under 60 chars.
- Blank line after the title, then literal `- `-prefixed bullets, each starting with an
  imperative verb (`Add`, `Remove`, `Update`, `Move`, `Rename`, `Fix`, `Pin`, `Enable`,
  `Disable`), capitalised, no trailing period. Group trivia, don't list every file.
- Host action required (new settings key, a config block to copy)? Final line:
  `Host action: <what to do>`.
- No co-author trailers, no "generated with" footers, no emoji.
- A commit changing a signal payload, a service signature, a settings key, or a default safety
  rail uses `!` and always gets a `Host action:` line.

Example:

```
chore(backend): add uv project config and tooling baseline

- Add backend/pyproject.toml with dependencies, dev/test dependency groups and uv default-groups
- Add ruff, mypy, pytest and coverage configuration
- Add commented banned-api table enforcing the no-inter-app-import rule
- Add MANIFEST.in, .python-version and .gitignore
```
