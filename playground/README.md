# django-dynamic-user playground

Phase 8, `docs/APP-DESIGN.md` §11.2 / `docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`'s own Phase 8
brief: two minimal Django+Next hosts, not one, proving both halves of `django-dynamic-user` agree
with each other over a real HTTP connection — and, uniquely for this app, that the swappable-model
story works end to end, not just in a unit test against `tests.backend.settings_swapped`. See
`FINDINGS.md` for what this actually found.

## What's here

| Path | What it is |
|---|---|
| `default/backend/` | A minimal Django host installing `dynamic_user` with **zero customization** — `AUTH_USER_MODEL = "dynamic_user.User"`, the package's own concrete models, path-linked to `../../../backend` via `[tool.uv.sources]` |
| `subclassed/backend/` | A host defining `core.User(dynamic_user.AbstractDynamicUser)` (+ `Profile`/`Setting`) with one extra field each, proving a host CAN extend all three models with zero package-level code changes |
| `default/frontend`, `subclassed/frontend` | Near-identical minimal Next App Router apps — self-service pages exercising every self-service hook, an admin panel exercising every admin hook. Deliberately duplicated, not shared: the only difference is the subclassed host's extra-field inputs |
| `docker-compose.yml` | One shared Postgres (two databases — see its own header comment for why one file, one Postgres), one shared Redis, both host stacks on distinct ports |

Both playground frontends join the **repo-root** npm workspace (`../package.json`), not a separate
one — same reasoning as `../frontend`'s own membership: one physical copy of
`react`/`@tanstack/react-query`/`@hjtdev/appkit` across the SDK under test and both hosts.

## Running it

```bash
# From the repo root:
npm install                                        # hoists frontend/'s deps for ALL THREE workspace members
cd frontend && npm run build && cd ../..            # path-linked SDK dist/ — build explicitly, it can go stale
cd playground/default/backend    && uv sync && cd ../../..
cd playground/subclassed/backend && uv sync && cd ../../..

docker compose -f playground/docker-compose.yml up -d --build --wait

docker compose -f playground/docker-compose.yml exec backend-default    python manage.py seed_users
docker compose -f playground/docker-compose.yml exec backend-subclassed python manage.py seed_users
```

Or via `make playground-up` from the repo root (does the same steps, minus seeding).

Then:

| Host | Frontend | Django admin (Jazzmin) | API direct |
|---|---|---|---|
| default | <http://localhost:3000> | <http://localhost:3000/admin/> | <http://localhost:8000> |
| subclassed | <http://localhost:3001> | <http://localhost:3001/admin/> | <http://localhost:8001> |

`manage.py seed_users` seeds four personas on each host, same credentials both sides
(password from `PLAYGROUND_PASSWORD`, default `playground-demo-not-a-secret` — see
`.env.example`):

| Username | Role |
|---|---|
| `super@playground.test` | superuser — can do everything on both hosts |
| `staff@playground.test` | `is_staff`, not superuser — admin on the default host (`ADMIN_REQUIRES_SUPERUSER=False`), **403 on the subclassed host** (`ADMIN_REQUIRES_SUPERUSER=True`) |
| `alice@playground.test` | plain user, public profile |
| `bob@playground.test` | plain user, private profile (`is_public=False`) |

Plus ~25 more plain users so `/profiles/` and the admin user list both span more than one page.

To reset the demo data without tearing the stack down: `make playground-reset` (both hosts), or
individually: `docker compose -f playground/docker-compose.yml exec backend-default python
manage.py seed_users --reset`.

## The two postures compared live

| | `default` (:8000/:3000) | `subclassed` (:8001/:3001) |
|---|---|---|
| `AUTH_USER_MODEL` | `dynamic_user.User` | `core.User` (+ `department`) |
| `DYNAMIC_USER_PROFILE_MODEL` | `dynamic_user.Profile` | `core.Profile` (+ `tagline`) |
| `DYNAMIC_USER_SETTING_MODEL` | `dynamic_user.Setting` | `core.Setting` (+ `theme`) |
| `ADMIN_REQUIRES_SUPERUSER` | `False` — staff can admin | `True` — superuser only |
| `DELETION_MODE` | `hard_delete` (the shipped default) | `anonymize` + `core.anonymize.anonymize_user` |
| Finalize path exercised | Celery beat (`worker-default`) | `manage.py process_deletion_requests` (no Celery) |

Logging into the SAME `staff@playground.test` account on both `:3000/admin-panel` and
`:3001/admin-panel` is the fastest way to see `ADMIN_REQUIRES_SUPERUSER`'s real effect without a
restart.

## Verification

```bash
# System checks, both hosts
docker compose -f playground/docker-compose.yml exec backend-default    python manage.py check
docker compose -f playground/docker-compose.yml exec backend-subclassed python manage.py check

# The live suites — real HTTP against the running stack, not Django's test client
cd playground/default/backend    && uv run pytest -m live
cd playground/subclassed/backend && uv run pytest -m live
```

The manual checks this was actually verified against — a real browser, both hosts side by side —
are recorded with full output in `FINDINGS.md`.
