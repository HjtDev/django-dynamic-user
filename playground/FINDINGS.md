# Phase 8 playground — findings

Phase 8, `docs/APP-DESIGN.md` §11.2 / `docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md`'s own Phase 8
brief: two minimal Django+Next hosts, proving both halves of `django-dynamic-user` agree with
each other over a real HTTP connection, and — uniquely for this app — that the swappable-model
story works end to end, not just in `tests.backend.settings_swapped`.

Everything below was observed against the real running stack
(`docker compose -f playground/docker-compose.yml up -d --wait`), not reasoned about. Where a
pytest or a `curl`/browser transcript demonstrates the behavior, it's quoted; four screenshots
from the actual browser session (`agent-browser`, headed CDP session, not simulated) are in
`playground/screenshots/`. As of this report:
`manage.py check` is clean on both hosts, 9/9 live tests pass on the default host, 10/10 pass on
the subclassed host (including the headline `test_extra_profile_field_round_trips`), and every
item on Phase 8's own checklist was exercised for real, not assumed.

## Summary

**No package-level bug was found.** Every discrepancy below was in this playground's own code
(two real bugs in tests I wrote, caught by running them) or a documentation gap worth naming for
Phase 9. `backend/src/` and `frontend/src/` are untouched — `git status` on both confirms it.

| # | Finding | Fix belongs in |
|---|---|---|
| 1 | My own live tests hit `/api/v1/admin/deletion-requests/` instead of `/api/v1/admin/users/deletion-requests/` — the admin basePath is `/api/v1/admin/users`, not `/api/v1/admin` | This playground's own test files — fixed here (§1 below) |
| 2 | The SDK's generated TypeScript types (`frontend/src/schema.d.ts`) know nothing about a subclassed host's extra fields (`tagline`/`theme`/`department`) — a page reading them needs a local type-widening cast | Expected, not a bug — worth a one-line callout in Phase 9's README frontend section (§2 below) |
| 3 | `django.contrib.auth.views.LogoutView` is POST-only as of Django 5.0 — a plain `<a href="/accounts/logout/">` 405s | This playground's own `Nav.tsx` — already built as a POST form with a CSRF hidden field, not a link; noted here so a future host copying this pattern doesn't rediscover it the hard way |
| 4 | `AccountDeletionRequest.user` is `on_delete=CASCADE` — after a `hard_delete` finalize, the request row itself is gone too, not left behind in a `finalized` state | Expected, not a bug — confirmed by design (§4 below); worth naming explicitly in Phase 9's docs since it's easy to assume `hard_delete` mode still leaves an audit trail row it doesn't |

## 1. Two wrong URLs in my own live test files — caught immediately by running them

**Fix belongs in: this playground's own test files (already fixed).**

Both `playground/default/backend/tests/live/test_default_playground.py` and
`playground/subclassed/backend/tests/live/test_subclassed_playground.py` originally called
`GET /api/v1/admin/deletion-requests/` — missing the `/users` segment `urls_admin.py`'s own
basePath (`/api/v1/admin/users/`) requires. First run:

```
FAILED tests/live/test_default_playground.py::test_finalize_deletion_request_is_superuser_only_regardless_of_admin_requires_superuser
json.decoder.JSONDecodeError: Expecting value: line 2 column 1 (char 1)
...
INFO httpx: HTTP Request: GET http://localhost:8000/api/v1/admin/deletion-requests/?status=approved "HTTP/1.1 404 Not Found"
```

Fixed to `/api/v1/admin/users/deletion-requests/` in both files. Re-run, both green:

```
tests/live/test_default_playground.py .................. 9 passed in 2.09s
tests/live/test_subclassed_playground.py ................ 10 passed in 3.19s
```

This is exactly the class of bug a playground exists to catch — a URL-shape assumption that a
unit test (which imports the URLconf directly and never hand-types a path string) can't surface,
but a real HTTP client absolutely does.

## 2. The extra-field headline check — confirmed three independent ways

**No fix needed — this is the positive result Phase 8 exists to prove.**

`tagline` exists only on `playground/subclassed/backend/core/models.py`'s `Profile` — zero lines
under `backend/src/` know it exists. Three independent proofs, in increasing order of realism:

**a) `pytest -m live`** — a real HTTP PATCH from an isolated Python process:

```
tests/live/test_subclassed_playground.py::test_extra_profile_field_round_trips PASSED
```

**b) A real browser session** (`agent-browser`, logged in as `alice` at `localhost:3001`) — read
the value pytest had written moments earlier, confirming both clients see the same server state:

```
textbox "tagline (core.Profile's own field)" [ref=e16]: Round-tripped live by the Phase 8 playground suite.
```

**c) A fresh browser-driven write, then a full page reload** — typed a new value
(`"Edited live through the Next.js UI, not curl."`), clicked Save, saw "Saved.", then navigated
away and back:

```
textbox "tagline (core.Profile's own field)" [ref=e16]: Edited live through the Next.js UI, not curl.
```

Same for `core.User.department` (read-only, `GET /me/`) and `core.Setting.theme` — both appear
correctly with zero `dynamic_user` code changes; the only reason they're visible at all is
`DYNAMIC_USER["USER_READ_FIELDS"]`/`PROFILE_EDITABLE_FIELDS`/`SETTING_EDITABLE_FIELDS` in
`playground/subclassed/backend/config/settings.py` naming them.

`git status` on `backend/` and `frontend/` (the package's own two halves) is clean throughout —
nothing under `src/` was touched to make any of this work.

## 3. Locked fields are genuinely non-editable through the UI — confirmed on both hosts

**No fix needed.**

`GET /me/` doesn't even expose `is_staff`/`is_superuser` by default — `USER_READ_FIELDS`'s
documented default is `["id","username","name","email","phone","is_active","date_joined"]`. What
it DOES expose renders as disabled inputs (`MeClient.tsx` renders every `/me/` field with
`disabled`), confirmed via `agent-browser` snapshot logged in as `staff` on the default host:

```
- textbox [disabled, ref=e19]: 2
- textbox [disabled, ref=e20]: staff
- textbox [disabled, ref=e22]: staff@playground.test
- textbox [disabled, ref=e24]: true          # is_active
- textbox [disabled, ref=e25]: 2026-09-04T16:50:37.625932Z
```

versus the editable `PROFILE_EDITABLE_FIELDS`/`SETTING_EDITABLE_FIELDS` sections directly below,
rendered as live `<input>`/`<textarea>` elements. Screenshot:
`01-default-me-locked-fields.png`.

## 4. The full deletion flow, both finalize paths, both `DELETION_MODE`s — confirmed live

**No fix needed — `AccountDeletionRequest`'s `CASCADE` behavior on `hard_delete` is by design,
worth naming explicitly in Phase 9's docs (not a defect).**

`seed_users` leaves one already-`approved`, backdated `AccountDeletionRequest` per host. Finalized
each through its OWN documented path — the celery-registered task directly on the default host,
the plain management command on the subclassed host (no Celery installed there at all):

```
$ docker compose exec backend-default python manage.py shell -c \
    "from dynamic_user.tasks import finalize_due_deletions; print('finalized:', finalize_due_deletions())"
finalized: 1

$ docker compose exec backend-subclassed python manage.py process_deletion_requests
Finalized 1 account deletion request(s).
```

Outcomes, confirmed via the admin API immediately after:

```
# default host (DELETION_MODE="hard_delete") — the user row is GONE
GET /api/v1/admin/users/?username=due-for-deletion  ->  {"count": 0, "results": []}

# subclassed host (DELETION_MODE="anonymize") — still present, scrubbed
GET /api/v1/admin/users/?id=30  ->  {
  "username": "deleted-user-30",
  "email": "deleted-30@anonymized.invalid",
  "is_active": false,
  "department": ""
}
```

On the default host, the finalized `AccountDeletionRequest` row is ALSO gone —
`AccountDeletionRequest.user` is `on_delete=CASCADE` (`backend/src/dynamic_user/models.py`), so a
hard-delete finalize takes the request row with it; there is no `status="finalized"` row left to
query. `GET /api/v1/admin/users/deletion-requests/?status=finalized` returns `count: 0` on the
default host, `count: 1` on the subclassed host (where the user row survives, so the request row
does too). This is correct, documented `on_delete` behavior — not a bug — but it's easy for a host
reading `DELETION_MODE="hard_delete"` to assume a request audit trail survives when it doesn't;
worth one sentence in Phase 9's README.

The `staff`-gets-403-on-finalize-regardless-of-`ADMIN_REQUIRES_SUPERUSER` gate was also exercised
live (both hosts) via `pytest -m live`'s
`test_finalize_deletion_request_is_superuser_only_regardless_of_admin_requires_superuser` /
`test_finalize_deletion_request_is_superuser_only_here_too` — both pass.

## 5. `ADMIN_REQUIRES_SUPERUSER`'s real effect — the SAME login, two different results

**No fix needed — this is the comparison Phase 8 asks for.**

`staff`/`playground-demo-not-a-secret` — identical credentials, identical seeded row, both hosts:

- `localhost:3000/admin-panel` (default, `ADMIN_REQUIRES_SUPERUSER=False`): full user list loads,
  29 users, pagination controls live.
- `localhost:3001/admin-panel` (subclassed, `ADMIN_REQUIRES_SUPERUSER=True`): page renders
  `"You do not have permission to perform this action. (status 403)"` — the appkit error
  envelope's own message, surfaced verbatim in the UI, not swallowed.

Screenshot: `03-subclassed-staff-403-admin-panel.png`.

## 6. `CanEscalatePrivilege` — a real 403, visible in the UI, not just curl

**No fix needed.**

Logged in as `staff` on the default host (where the general admin gate DOES admit staff), opened
`user01`'s manage panel, ticked `is_staff`, clicked "Save is_staff":

```
Only a superuser may set the following field(s): is_staff. (status 403)
```

Rendered directly in the page — `CanEscalatePrivilege`'s own `self.message`, unmodified, via
appkit's error envelope. The same action as `super` succeeds (`pytest`'s
`test_staff_cannot_escalate_privilege_but_superuser_can`, both hosts, both pass) and the change is
reverted by the test itself so a re-run stays deterministic. Screenshot:
`02-default-staff-escalation-403.png`.

## 7. Pagination — confirmed past page 1, both surfaces, both hosts

**No fix needed.** `usePublicProfiles`/`useAdminUsers` both paginate correctly:

```
tests/live/test_default_playground.py::test_public_profiles_list_excludes_private_and_paginates PASSED
tests/live/test_subclassed_playground.py::test_public_profiles_list_paginates PASSED
```

Live in the browser: `admin-panel` showed "Admin — users (29 total)" with `← prev` disabled and
`next →` enabled on page 1.

## 8. Jazzmin admin shows the same data as the API path — confirmed on both hosts

**No fix needed.**

Session login (`super`, cookie-based CSRF) against each host's own model namespace — `dynamic_user`
on the default host, `core` on the subclassed host (the swappable models' app label follows
wherever the host mounted them):

```
$ curl (session as super) http://localhost:8000/admin/dynamic_user/  -> 200
  User, Profile, Setting, Account deletion request

$ curl (session as super) http://localhost:8001/admin/core/          -> 200
  User, Profile, Setting
$ curl (session as super) http://localhost:8001/admin/dynamic_user/  -> 200
  Account deletion request   # not swappable — stays under dynamic_user's own label on both hosts
```

## What was NOT found

- No missing `appkit` wiring surprise (unlike `cleanup_app`'s own Phase 7 playground, which
  found this live) — `config/settings.py` on both hosts was written with the full `appkit`
  baseline from the start, informed by that prior finding.
- No Turbopack `root`/rewrite trailing-slash issues — both known traps
  (`../cleanup_app/playground/FINDINGS.md` #1–#2) were designed around from the start; confirmed
  clean by every page returning 200 with no error overlay and `/admin/login/` not looping.
- No `manage.py check` warnings on either host (all 14 throttle scopes present, `NUM_PROXIES`/
  `APPKIT["TRUSTED_PROXY_COUNT"]` agree, `RequestIDMiddleware` positioned correctly).
- `django-jazzmin>=3.0` resolved cleanly against this app's own `django>=5.2,<7.0` range (`django
  6.0.8`/`6.1.1` resolved on the two hosts respectively) — no version conflict.
