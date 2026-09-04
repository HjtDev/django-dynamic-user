# SECURITY-CHECKLIST.md

Phase 10's walk of `docs/APP-DESIGN.md` §9 (backend) and §12 (frontend), against `v1.0.0`. Every
line below is evidence — a file:line, a test name plus real command output, or a grep run and
its actual result — never a citation of an earlier phase's memory. Commands were run against a
fresh clone-equivalent state on 2026-09-05; see the raw output pasted into the Phase 10 PR
description for the full logs this table summarizes.

## §9 — Backend

| Item | Evidence |
|---|---|
| No unauthenticated writes | Every view in `views.py`/`admin_views.py` declares `permission_classes` — `IsAuthenticated` at minimum, `IsDynamicUserAdmin` on every admin route. `tests/backend/test_views.py`, `test_admin_views.py`, and their swapped-leg twins assert 401/403 for an unauthenticated or under-permissioned caller. |
| **Object-level checks / IDOR** | `IsProfileOwner`/`IsPublicOrOwner` (`permissions.py`) sit on top of the class-level `IsAuthenticated` gate. `tests/backend/test_permissions.py:37` (`test_is_profile_owner_denies_a_foreign_object`) and `:58` (`test_is_public_or_owner_raises_not_found_for_a_stranger_when_private`) prove a stranger gets **404, not 403**, for a private profile — its existence doesn't leak through the status code. `test_views.py:245` and the swapped-leg twin `test_views_swapped.py:103` prove the same at the view layer. |
| No blanket `fields = "__all__"` | `grep -rn '"__all__"' backend/src` → clean. Every writable serializer is built by `build_serializer()` from an explicit `DYNAMIC_USER` field list, validated against the resolved model by `dynamic_user.E005`. |
| No password/hash in read output | `build_serializer()` hard-refuses `password` unconditionally, even if explicitly requested or reached through a `source=` alias. Proven fresh: `uv run pytest -k password` → `test_admin.py::test_user_change_form_exposes_password_only_via_readonly_hash_field`, `test_admin_views.py::test_admin_user_list_password_never_appears`, `test_admin_views.py::test_admin_user_detail_returns_full_fields_except_password`, `test_serializers.py::test_password_in_fields_is_refused`, `test_serializers.py::test_password_reached_via_a_source_alias_is_refused`, `test_serializers.py::test_admin_user_serializer_includes_real_fields_and_excludes_password` — **6 passed**. |
| No raw SQL | `grep -rn '\.raw(\|RawSQL\|extra(select' backend/src` → clean. `ruff`'s `S` (bandit) ruleset runs over `backend/src` and `../tests` in `make lint` → all checks passed. |
| File uploads validate server-side | `AvatarMixin` (`mixins.py`) declares a real `ImageField`; validation is Django's own field-level `ImageField` type/size checks plus whatever `hjtdev-appkit[images]`'s own validators enforce (an app dependency, not reimplemented here). Covered by `test_mixins.py`. |
| **No secrets or keys hardcoded** | This package defines **zero** credentials of its own and reads **zero** `.env` keys — `README.md`'s "Required `.env` keys" section says so explicitly. `grep -rniE 'SECRET|API_KEY|_TOKEN\s*=|PASSWORD\s*=' backend/src` → the only hit is a docstring in `managers.py` describing Django's own `create_superuser(username, email, password, ...)` signature, not a real credential. |
| Rate limiting + admin/user separation | All 14 `throttle_scope` values (6 self-service, 8 admin) are distinct and documented in `README.md`'s endpoint tables; `readme-contract`'s scope-presence check passes locally. `IsDynamicUserAdmin` (admin surface) vs. `IsProfileOwner`/`IsPublicOrOwner` (self-service) are never interchangeable — `ADMIN_REQUIRES_SUPERUSER` tightens the admin gate to `is_superuser` without ever relaxing the self-service one. |
| **Privilege-escalation guard** | `CanEscalatePrivilege` rejects any admin `PATCH` touching `is_staff`/`is_superuser`/`is_active`/`groups`/`user_permissions` unless `request.user.is_superuser` is `True`, independent of `ADMIN_REQUIRES_SUPERUSER`. **Re-run fresh for this release, both legs**, ephemeral Postgres up, no cached result: default settings — `uv run pytest -k "escalat or finalize_403" -v --no-cov` → **10 passed** (`test_staff_admin_cannot_escalate_another_users_privileges` ×4 params, `test_staff_admin_cannot_escalate_their_own_privileges` ×3 params, `test_staff_admin_escalation_attempt_rejects_the_whole_request_not_just_the_field`, `test_escalation_guard_still_runs_when_admin_requires_superuser_is_true`, `test_finalize_403s_a_plain_staff_admin_even_under_the_default_setting`); `settings_swapped` — `DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped uv run pytest -k escalat -v --no-cov` → **10 passed**, including `test_admin_views_swapped.py::test_staff_admin_cannot_escalate_privileges_on_the_swapped_user_model`. The guard holds against the resolved (possibly subclassed) user model, not just the default one. |
| `pip-audit` / `npm audit` | `uvx pip-audit --strict --no-deps -r <(uv export --locked --no-default-groups --all-extras --no-hashes --format requirements-txt | grep -v '^-e ')` → **No known vulnerabilities found** (both extras — `celery`, `avatar` — included). `npm audit --audit-level=high` (repo-root workspace) → **found 0 vulnerabilities**. |
| Dependency ranges | `uv sync --resolution lowest-direct --upgrade --extra celery --extra avatar && uv run pytest -n auto --no-cov` → **282 passed, 33 skipped** at the declared floor (Django 5.2, DRF 3.15, drf-spectacular 0.27, `hjtdev-appkit` 2.0.0) — the ranges in `[project.dependencies]` genuinely work, not just the locked versions. Lockfile install restored afterward via `uv sync --locked`. |

## §12 — Frontend

| Item | Evidence |
|---|---|
| No token/key storage from package code | `grep -rn "localStorage\|sessionStorage" frontend/src` → clean. The SDK relies entirely on the host's own auth/cookie handling via the injected `HttpClient`. |
| Managers never build a URL from unescaped input | Both manager classes (`DynamicUserManager`, `DynamicUserAdminManager` in `api/manager.ts`) interpolate only numeric ids and route through `toQueryString()` for params — no string concatenation of free-text user input into a path. |
| No `dangerouslySetInnerHTML` | `grep -rn "dangerouslySetInnerHTML" frontend/src` → clean. The package ships hooks only, no rendered components. |
| No hardcoded base URL/secrets | `grep -rn "http://\|https://\|localhost" frontend/src` → the only hits are `schema.d.ts`'s auto-generated pagination `@example` JSDoc comments (from `drf-spectacular`'s own OpenAPI examples), not a real URL used at runtime. `basepath-routing.test.tsx` proves `basePath` always comes from `useApiClient()`'s context, never a literal. |
| **Destructive/admin mutation hooks never fire on mount** | `tests/frontend/mutations-do-not-fire-on-mount.test.tsx` originally covered 5 of this SDK's 9 mutation hooks. **Gap found and closed this phase**: added the 4 missing cases — `useUpdateMyProfile`, `useUpdateMySetting`, `useUpdateAdminUserProfile`, `useUpdateAdminUserSetting` — each mounts the hook, rerenders twice, flushes a microtask, asserts `isIdle`/zero calls, then calls `mutate()` and asserts exactly one call. Re-ran: `npx vitest run --no-coverage tests/frontend/mutations-do-not-fire-on-mount.test.tsx` → **9 passed** (up from 5). Full suite after the addition: **24 test files, 57 tests passed** (up from 53), coverage unchanged at 99.41% statements / 100% functions / 100% lines. |
| Typed end-to-end, no `any` | `grep -rn ": any\|<any>\|as any" frontend/src --include="*.ts"` (excluding the generated `schema.d.ts`) → clean. `npx tsc --noEmit` under `"strict": true` → passes as part of `make check`. |
| `peerDependencies` only, zero bundled runtime deps | `frontend/package.json` declares `react`, `@tanstack/react-query`, `@hjtdev/appkit` as `peerDependencies` and carries **no** `dependencies` key at all — enforced going forward by CI's `forbid-runtime-dependencies: true` input. |
| `npm audit --audit-level=high` | 0 vulnerabilities (see §9 table above — one combined run covers both). |

## Supply chain (§9, shared)

- `uv tree` reviewed before adding anything new to `[project.dependencies]`/`[project.optional-dependencies]` — no new dependency was added in this phase; the CI file only *invokes* tooling (`pip-audit`, `npm audit`) that already existed as a Makefile/README-documented command.
- Wheel contents verified directly, not assumed: rebuilt (`rm -rf dist && uv build`) and inspected — contains `dynamic_user/py.typed` and `dynamic_user/locale/fa/LC_MESSAGES/django.mo`, both asserted by CI's `wheel-must-contain`. Smoke-installed into a clean venv (`uv venv /tmp/smoke && uv pip install ... && python -c "import dynamic_user"`) → `import ok`.
- Three CI grep backstops reproduced locally and clean: no sibling-app import, no `factories.py` import outside itself, no host-module (`tools`/`core`/`config`) import.

## Outcome

No unresolved §9/§12 item. One real gap was found (frontend mutation-mount coverage, 5/9 hooks)
and fixed in this same phase rather than deferred — see `tests/frontend/mutations-do-not-fire-on-mount.test.tsx`.
