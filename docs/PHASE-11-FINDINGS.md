# Phase 11 findings — installing `django-dynamic-user` v1.0.0 into a real host, twice

Phase 11, per `docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`'s own prompt: install the package
into a fresh `base-scaffold` clone, twice — once accepting every default model, once subclassing
all three — following `docs/INTEGRATION-GUIDE.md` §2's 15-step protocol, using **only
`README.md`** for configuration values. No inside knowledge of the package's own source was used
to fill a gap; every value came from the README as published, or was derived on the spot when the
README didn't say.

Both halves are confirmed live on the public registries at the tag installed: PyPI
`django-dynamic-user==1.0.0`, npm `@hjtdev/django-dynamic-user@1.0.0`, `hjtdev-appkit==2.0.1`
resolved transitively. The published `README.md` at tag `v1.0.0` is byte-identical to this
repo's working tree (`diff` confirmed before starting).

Two throwaway host clones did the work: `~/Projects/phase11-default-host` (`PROJECT_NAME=p11default`,
ports 8000/3000/5432/6379) and `~/Projects/phase11-subclassed-host` (`PROJECT_NAME=p11sub`, ports
8010/3010/5442/6389). Neither is part of this repo.

## Summary

**One severe finding, several real-but-recoverable friction points, and one finding that
overturns a documented failure-mode claim.**

| # | Finding | Severity | Fix belongs in |
|---|---|---|---|
| 1 | Subclassing example omits `INSTALLED_APPS += ["dynamic_user"]` entirely — following it literally crashes at startup with `RuntimeError` | **Severe** | README.md — fixed here |
| 2 | The "copy this block verbatim" settings block has no marked insertion point and NameErrors if pasted at the file's only marked spot | Real | README.md — fixed here |
| 3 | The pasted settings block fails `ruff format --check` as written | Minor | README.md — fixed here |
| 4 | The pasted settings block fails `mypy` under django-stubs unless `REST_FRAMEWORK` carries a type annotation | Real, but arguably base-scaffold's own gap | README.md note — fixed here |
| 5 | `urls.py` snippet is missing `from django.urls import include` | Real | README.md — fixed here |
| 6 | The subclassing example's `objects = UserManager()` line fails `mypy` under django-stubs | Real | README.md — fixed here |
| 7 | The subclassing example's import block isn't `ruff`-import-sort-clean | Minor | README.md — fixed here |
| 8 | **The documented "forgot the admin basePath" failure mode does not occur** — confirmed live, twice, with the real shipped SDK | Overturns a claim | README.md — corrected here |
| 9 | `app/providers.tsx` example imports `makeQueryClient` from a `@/lib/query-client` module that doesn't exist in base-scaffold | Real | README.md — fixed here |
| 10 | Assorted smaller doc gaps ("two"/"three" settings count needed a clarifying note; no smoke-test step; "weekly" schedule has no day/hour; system-check table skips E004) | Minor | README.md — fixed here |

No package-level (`backend/src/dynamic_user/`, `frontend/src/`) code was touched to make any of
this work — `git status` on this repo confirms it throughout. Every fix below is a `README.md`
change (synced to `backend/README.md`/`frontend/README.md`), not a code change — per this repo's
CLAUDE.md working agreement, a code-level fix is flagged for the user's decision instead of made
here.

---

## 1. Severe: the subclassing example crashes at startup as written

**Fix belongs in: README.md's "Worked subclassing example" section.**

The section (`README.md` lines 69–125 at the time of this run) shows exactly one `INSTALLED_APPS`
change:

```python
INSTALLED_APPS += ["core"]  # must be installed BEFORE "dynamic_user" is added, or Django's
                             # swappable-model resolution can't find it at migration time
```

That comment implies `"dynamic_user"` gets added too, but the example never shows it, and no
other part of the subclassing section says to. Following the section exactly — `core/models.py`
as shown, then only `INSTALLED_APPS += ["core"]`, `AUTH_USER_MODEL`/the two swappable-model
settings, and the three-key `DYNAMIC_USER` dict — produces this at the very first
`manage.py check`:

```
RuntimeError: Model class dynamic_user.models.User doesn't declare an explicit app_label and
isn't in an application in INSTALLED_APPS.
```

**Why:** `core/models.py`'s own required import —
`from dynamic_user.models import AbstractDynamicUser, AbstractProfile, AbstractSetting` — also
imports that module's top-level, *unconditionally defined* concrete `User`/`Profile`/`Setting`
classes (the ones a default host uses as-is). Importing the module registers those classes with
Django's app registry regardless of whether they're the active swapped-in models, and Django's
model metaclass requires their app to be in `INSTALLED_APPS` to resolve an `app_label` — even
though a subclassed host never uses them.

**Confirmed already handled correctly, but undocumented:** `playground/subclassed/backend/config/settings.py`
(this repo's own working example) *does* add `INSTALLED_APPS += ["dynamic_user"]` — via the exact
same `# ---- DYNAMIC_USER WIRING adds "dynamic_user" below ----` block the default host uses. The
"Worked subclassing example" section in the README, however, never shows or mentions this step.
Phase 8/9's own playground silently avoided this bug by copying the default-host wiring block
even in the subclassed host; the README's *subclassing-specific* section never says to.

**Fix applied here:** the README's subclassing example now says explicitly that `"dynamic_user"`
still goes in `INSTALLED_APPS` even when every model is subclassed, with the reason (the
unconditional import above), right next to the `"core"` line.

## 2. The settings block has no marked insertion point, and NameErrors at the obvious one

**Fix belongs in: README.md's settings section — a placement note added.**

`backend/config/settings.py`'s own file-level docstring and its `INSTALLED_APPS`/`MIDDLEWARE`
lists are the *only* marked insertion points in the whole file:

```python
INSTALLED_APPS = [
    ...
    # ---- installed app packages get added here, one line each, per their own README
]
MIDDLEWARE = [
    ...
    # ---- installed app packages append their middleware here, per their own README
]
```

The README's own "copy this block verbatim" instruction gives one monolithic chunk —
`INSTALLED_APPS += [...]`, `MIDDLEWARE += [...]`, then
`REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({...})`, then the three model settings — with no
stated position. Pasting it at the file's only marked spot (right after the base
`INSTALLED_APPS`/`MIDDLEWARE` list definitions, which is the natural reading of "append here")
crashes immediately:

```
NameError: name 'REST_FRAMEWORK' is not defined
```

`REST_FRAMEWORK` isn't defined until much later in `settings.py` (the "DRF / schema" section).
The block has to go **after** that dict is defined — confirmed by moving it there, which resolved
cleanly (`manage.py check`: `System check identified no issues`).

**Fix applied here:** the README's settings section now states explicitly that the whole block
goes after `REST_FRAMEWORK` is defined, not at the `INSTALLED_APPS`/`MIDDLEWARE` marker comments.

## 3. The pasted block isn't `ruff format`-clean

**Fix belongs in: README.md — a one-line note.**

After correcting the placement (finding #2), `make check`'s lint leg still failed:

```
cd backend && uv run ruff check . && uv run ruff format --check .
All checks passed!
unformatted: File would be reformatted
 --> config/settings.py:161:49
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    ...
})
```

`ruff format` wants the `.update(...)` call's dict argument on its own indented line, not hugging
the call parens the way the README's snippet is formatted. `uv run ruff format .` fixes it in one
step — this is not a bug, just worth a one-line "run `ruff format` after pasting" note so a host
doesn't wonder why `make check` fails on an untouched paste.

## 4. `mypy` fails on the pasted block: `REST_FRAMEWORK` needs a type annotation

**Fix belongs in: README.md note (the underlying gap is arguably base-scaffold's own).**

After fixing #2 and #3, `make check`'s typecheck leg still failed:

```
cd backend && uv run mypy .
config/settings.py:161: error: "object" has no attribute "update"  [attr-defined]
```

`backend/config/settings.py`'s own `REST_FRAMEWORK = {...}` dict literal (base-scaffold's own
file, unmodified) has no type annotation. Because its values are a heterogeneous mix (strings, a
list, an empty dict, an int), mypy infers a narrow common type for `DEFAULT_THROTTLE_RATES` that
doesn't support `.update()`. The scaffold's own `APPKIT` dict two sections below is already
annotated `APPKIT: dict[str, Any] = {...}` for exactly this reason — `REST_FRAMEWORK` isn't.

**Fix applied here:** `REST_FRAMEWORK: dict[str, Any] = {` is the annotation that resolves it
(confirmed: `mypy` clean afterward, both hosts). Added as a note in the README's settings section,
since the block instructs a `.update()` call into a dict the README doesn't control the
declaration of.

## 5. `urls.py` snippet is missing `from django.urls import include`

**Fix belongs in: README.md's URL mounting section.**

```python
urlpatterns = [
    ...
    path("api/v1/users/", include("dynamic_user.urls")),
    path("api/v1/admin/users/", include("dynamic_user.urls_admin")),
]
```

`include` is used but never imported in the snippet, and base-scaffold's own `urls.py` only
imports `path`. Copying the snippet as shown fails with `NameError: name 'include' is not
defined`. Fixed here by adding the import to the README's snippet.

## 6. Subclassing example's `objects = UserManager()` fails `mypy`

**Fix belongs in: README.md's subclassing example.**

```
core/models.py:12: error: Cannot override class variable (previously declared on base class
"AbstractDynamicUser") with instance variable  [misc]
```

The README's own snippet has a bare `objects = UserManager()` on the subclass. Under
`django-stubs`' mypy plugin, this collides with the base class's own (also bare) declaration.
`playground/subclassed/backend/core/models.py` has the identical line and never hit this, because
**that playground has no `[tool.mypy]`/django-stubs configuration at all** — this run is the
first time this exact README snippet has ever been checked by mypy.

**Fix applied here:** annotate as `objects: ClassVar[UserManager] = UserManager()` (with
`from typing import ClassVar` added to the snippet's imports). Confirmed clean afterward.

## 7. Subclassing example's import block isn't import-sort-clean

**Fix belongs in: README.md's subclassing example (minor).**

```
I001 Import block is un-sorted or un-formatted
 --> core/models.py:1:1
```

The README's snippet groups `django.db` and the two `dynamic_user` imports with a blank line in
between; base-scaffold's ruff isort config wants them in one block, no blank line. `ruff check
--fix` resolves it automatically — noted here only because the doc claims this snippet is
lint-clean by omission.

## 8. The "forgot the admin basePath" failure mode does not occur — confirmed live, twice

**Fix belongs in: README.md's basePaths warning — corrected, not just softened.**

`README.md`'s "Usage" section carries a bolded warning:

> **This app registers two API surfaces, not one** — `dynamic_user` (self-service) and
> `dynamic_user_admin` (admin). A host wiring only `dynamic_user` will see every admin hook 404
> or hit the self-service prefix instead...

`docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md` §4 names this as a documented failure mode whose
guard is "Phase 11 installs and checks both." This run built exactly that test — a page importing
one self-service hook (`useMe`) and one admin hook (`useAdminUsers`), first with `basePaths`
missing the `dynamic_user_admin` key entirely, then with both keys present — and ran it two ways:

1. **Read the actual shipped code.** `node_modules/@hjtdev/appkit/dist/provider.js`'s
   `useApiClient(key, defaultBasePath)`:
   ```js
   const resolvedBasePath = normalizeBasePath(context.basePaths[key] ?? defaultBasePath);
   ```
   `node_modules/@hjtdev/django-dynamic-user/dist/api/config.js`:
   ```js
   export const useDynamicUserAdminConfig = () => useApiClient("dynamic_user_admin", "/api/v1/admin/users");
   ```
   The fallback default (`/api/v1/admin/users`) is **exactly** the README's own recommended
   backend mount path.

2. **Ran it live, twice** (once per host), from Node against the real running backend — no CORS,
   real HTTP, the actual `DynamicUserAdminManager` class from the installed package:
   ```
   === Scenario A: dynamic_user_admin key OMITTED ===
   resolved admin basePath: /api/v1/admin/users
   useAdminUsers() network result: { status: 200, url: '.../api/v1/admin/users/', body: '{"count":1,...' }

   === Scenario B: both keys registered ===
   resolved admin basePath: /api/v1/admin/users
   useAdminUsers() network result: { status: 200, url: '.../api/v1/admin/users/', body: '{"count":1,...' }
   ```
   **Byte-identical results.** Reproduced on both hosts (default: port 8000; subclassed: port
   8010) with real seeded users and real Basic-auth credentials.

**Conclusion:** for any host that mounted the backend URLs at the README's own recommended paths
(`api/v1/users/` / `api/v1/admin/users/` — which is what the URL-mounting section instructs), a
missing `dynamic_user_admin` `basePaths` entry has **zero observable effect**, because appkit's
own documented fallback-to-app-default behavior happens to equal the correct URL. The warning as
worded describes a failure that would only occur if a host *also* chose a non-default backend
mount path while separately forgetting the `basePaths` key — a compound, unstated precondition,
not "wiring only `dynamic_user`" on its own.

This is worth restating carefully rather than just deleting the warning: it is *good practice* to
register both keys explicitly (a host that later remounts the backend at a different prefix would
otherwise get a silent, hard-to-diagnose failure instead of a build-time or config-time signal),
but the README currently states this as an active bug a host will *see*, and it doesn't, under the
setup the README itself walks a host through. Fixed here to describe the real risk (a *future*
remount silently falling back) rather than a failure that doesn't reproduce.

## 9. `app/providers.tsx` example imports a module that doesn't exist

**Fix belongs in: README.md's "Usage" section.**

```tsx
import { makeQueryClient } from "@/lib/query-client";
```

`frontend/lib/query-client.ts` does not exist in base-scaffold — confirmed on both hosts
(`find frontend/lib -type f` shows only `api-client.ts`). Per `INTEGRATION-GUIDE.md` §6,
`makeQueryClient()` is exported from `@hjtdev/appkit` itself; base-scaffold's own real
`app/providers.tsx` (both this run's hosts, unmodified from the scaffold) imports it from there:

```tsx
import { ApiClientProvider, makeQueryClient } from "@hjtdev/appkit";
```

The README's snippet, copied as shown, fails to resolve the import. Fixed here to match what a
real base-scaffold host actually has.

## 10. Smaller documentation gaps, confirmed or carried over

- **"Two" vs "three" swappable-model settings.** The heading says "two" (matching this repo's own
  `CLAUDE.md` convention, which counts only the two settings this package itself defines —
  `DYNAMIC_USER_PROFILE_MODEL`/`DYNAMIC_USER_SETTING_MODEL` — treating `AUTH_USER_MODEL` as
  Django's own setting, reused rather than duplicated), but the body and table both plainly cover
  three settings and say "all three" twice. Not actually a contradiction once the convention is
  understood, but genuinely confusing on a cold read — added one clarifying sentence under the
  heading rather than changing the count, to stay consistent with `CLAUDE.md`'s own semver-trigger
  wording.
- **No smoke-test step anywhere in the install flow.** Nothing in the README tells a host how to
  confirm the install actually worked (no `createsuperuser` mention, no "hit this URL and expect
  this" step). This run improvised one (create a superuser via shell, curl `/me/`, curl the admin
  list, check swagger-ui) — added as a short "Verifying the install" note.
- **The recommended periodic schedule gives no day/hour for the weekly task.**
  `dynamic_user.tasks.purge_deletion_history — weekly` has no further detail; `finalize_due_deletions`
  at least says "daily at 03:00." This run picked Sunday 04:00 UTC arbitrarily for its own
  `PeriodicTask` data migration — noted as the README's own gap, not resolved with a hardcoded
  recommendation (the choice is genuinely host-specific), but the README now says explicitly that
  a host must pick both.
- **System-check table skips `dynamic_user.E004`.** The table lists E001, E002, E003, then jumps
  to E005. The installed package's own `checks.py` docstring names E004 as "reserved for Phase 2:
  the resolved model does not subclass this app's abstract base" — added to the table.
- **DRF authentication worked without any documented configuration**, confirmed live (Basic auth,
  DRF's own default `DEFAULT_AUTHENTICATION_CLASSES`, no `auth-app` installed) — this turned out
  *not* to be a gap in practice for local/curl-driven verification, so no README change here, but
  worth a footnote that a real host still needs its own `auth-app` or session-cookie strategy for
  a browser UI to authenticate cross-origin (this run's browser-side check used direct
  Node-side Basic auth against the API, not a logged-in browser session, specifically because the
  scaffold has no auth wired by design).

## What was NOT found

- **Zero `.env` keys required**, confirmed by diffing `backend/.env.example` against the working
  `backend/.env` on both hosts — only `SECRET_KEY`, `FERNET_KEY`, and `POSTGRES_PASSWORD` changed
  from their placeholders, none of them `dynamic_user`-specific. The README's claim ("None. Zero
  `.env` keys...") holds.
- **Jazzmin sidebar entries appear correctly with only the documented `icons` block added** — no
  further `JAZZMIN_SETTINGS` edits, on both hosts, confirmed via authenticated session requests to
  `/admin/` (not just curl to an endpoint — the actual rendered admin index page, logged in as a
  real superuser).
- **The subclassed extra fields round-trip over real HTTP with zero package-level changes** —
  `tagline` (PATCH `/api/v1/users/me/profile/`) and `theme` (PATCH `/api/v1/users/me/setting/`),
  confirmed via curl, with the round-tripped values read back on a fresh `GET`. `git status`-style
  diff of `.venv/site-packages/dynamic_user` and `node_modules/@hjtdev/django-dynamic-user`
  confirmed only `.pyc` bytecode caches changed, no `.py`/`.js`/`.ts` source.
- **The account-deletion flow works end to end on both hosts**, via each host's own documented
  path — the celery task (`finalize_due_deletions`, default host, which took the `[celery]`
  extra) and the plain management command (`process_deletion_requests`, subclassed host, which did
  not) — both hard-deleting the requesting user as `DELETION_MODE`'s documented default.
- **`hjtdev-appkit` resolved transitively with zero separate install step**, exactly as the README
  claims — confirmed via `uv tree` on both hosts.
- **The OpenAPI schema carries both `dynamic-user` and `dynamic-user-admin` tags**, and
  `/api/schema/swagger-ui/` renders 200, on both hosts.

## Environment artifacts that are NOT findings

Two things briefly looked like package bugs and weren't:

- **`InconsistentMigrationHistory` on the default host's first real boot.** Caused by this run's
  own earlier baseline check (confirming the *bare* scaffold boots before installing anything),
  which let Django's default `auth.User` migrate before `AUTH_USER_MODEL` was ever set. Resolved
  by `docker compose down -v` (fresh DB volume) before installing the package — a real host
  wouldn't hit this, since `AUTH_USER_MODEL` is set before the *first* `migrate` ever runs, per
  the README's own "pre-first-migrate decision" warning.
- **`EACCES` on `frontend/.next/trace` during `make check`'s build leg, twice.** The frontend dev
  container (bind-mounting `frontend/`) was still running and had written root-owned files into
  `.next/` on the host filesystem; the host-side `npm run build` couldn't write there as a normal
  user. Resolved by stopping the container and clearing the root-owned directory before running
  the build outside Docker. Unrelated to `django-dynamic-user`.
