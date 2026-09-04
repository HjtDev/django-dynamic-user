# CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md — Building `django-dynamic-user`

Project-specific instance of `docs/CLAUDE-CODE-GUIDE-APP.md`, pre-customized so each phase is a
paste-and-go session instead of a re-derive-the-prompt-in-Opus session. **This file is what you
follow phase by phase.** The generic guide stays as reference for *why* each phase is shaped this
way; this one has already made every project-specific call the generic guide's §1.3 table asks
for (see §1 below), so no session needs to re-decide them.

> Companions: `docs/APP-DESIGN.md` (the architecture every app package follows),
> `docs/CLAUDE-CODE-GUIDE-APP.md` (the generic process this document instantiates),
> `docs/INTEGRATION-GUIDE.md` (the host side), `docs/BASE-DESIGN.md` (what a host provides).

---

## 0. What this app is, and the three constraints unique to it

A reusable Django + React app package that **is** a host project's user data layer: `User`,
`Profile`, and `Setting` models a host installs, optionally subclasses for its own fields, and
wires up via `AUTH_USER_MODEL` (mandatory — this app's `User` is meant to *be* the project's user
model, not sit alongside Django's default one) plus two companion settings. It ships self-service
API views (see your own info, edit your own profile/settings, browse other users' public
profiles), a parallel admin API + Jazzmin admin surface with full read/write power over everyone,
an opt-out account-deletion request flow reviewable from both interfaces, a small library of
optional mixins (`Avatar`, `Timestamp`, `History`, `SoftDelete`, `Verification`, `LastSeen`,
`Metadata`) a host's own subclass can add in, and frontend hooks/managers for both surfaces.

**This app deliberately does not do authentication.** No registration endpoint, no login, no JWT,
no password reset. Those belong to a separate `auth-app` package (`BASE-DESIGN.md` §11.3 already
reserves this name) that depends on this app only through `get_user_model()` — exactly the way
Django's own `django.contrib.auth` views depend on whatever `AUTH_USER_MODEL` resolves to, never a
concrete import. Building this app first and an auth app second is deliberate: the swappable-model
machinery below is easier to get right without a login flow simultaneously depending on it.

Same operating principle as every app package (`CLAUDE-CODE-GUIDE-APP.md` §0): a contract before
code, machine-enforced boundaries from Phase 1. Three things are unique to *this* app and apply to
every phase below without exception:

1. **Every model reference inside this package is indirect, always.** `settings.AUTH_USER_MODEL`
   for the user, and two resolver functions — `dynamic_user.resolution.get_profile_model()` /
   `get_setting_model()` — for the other two, mirroring how `django.contrib.auth.get_user_model()`
   itself works. **Never** `from dynamic_user.models import User` — not even inside this package's
   own `services.py` or `admin.py`. This app's *entire reason to exist* is that a host can swap
   each of the three models out for its own subclass; a single concrete import anywhere breaks
   every host that does. Grep for `from .models import` or `from dynamic_user.models import` at
   the end of every phase that touches business logic — finding one is not a style nit, it's a
   phase that isn't done.
2. **A settings change must never produce a migration diff.** Field allowlists
   (`USER_EDITABLE_FIELDS`, `PROFILE_PUBLIC_FIELDS`, …), region-specific validators
   (`PHONE_VALIDATORS`, `NAME_VALIDATORS`), and anything else configurable are all resolved at
   *call* time — inside a serializer factory function, a validator wrapper, a permission check —
   never baked into a `models.py` class attribute. The one deliberate exception, forced by Django
   itself, is `USERNAME_FIELD`/`REQUIRED_FIELDS` on the abstract base: those genuinely are class
   attributes Django's auth machinery reads at class-definition time, so changing them **is** a
   schema-affecting decision a host makes once, consciously, before its first `migrate` — document
   this exception explicitly everywhere it's relevant rather than let it read as a contradiction of
   the rule above.
3. **This app holds credentials and PII — treat every serializer and every admin surface as a
   security review, not a CRUD exercise.** No serializer, in any surface, ever emits `password` or
   a raw password hash. No non-superuser-gated code path ever writes `is_staff`, `is_superuser`, or
   `is_active` on any user, including the requesting user's own row. A public-profile response
   exposes exactly the settings-declared allowlist intersected with the resolved model's real
   fields — never a `fields = "__all__"` fallback, and never "public unless the host says
   otherwise." Region-specific validators (phone, name) must fail closed: an unconfigured or
   unresolvable validator path rejects input rather than silently accepting anything.

---

## 1. Decisions already made (the generic guide's §1.3 table, answered)

Read this once; every phase prompt below assumes it.

| Question | Decision |
|---|---|
| Importable module name | **`dynamic_user`** — verified unclaimed in this ecosystem's own installed apps (`cleanup_app`, `appkit`) and not a name any current dependency owns |
| PyPI distribution | **`django-dynamic-user`** (unprefixed — verified free at the time this guide was written; re-verify in Phase 10 per that phase's own step 1, since time passes between writing this guide and tagging) |
| npm package | **`@hjtdev/django-dynamic-user`** (scoped, matching `@hjtdev/appkit` and `@hjtdev/django-cleanup` — every other SDK in this ecosystem is `@hjtdev`-scoped, and an unscoped name can be squatted out from under a later release) |
| GitHub repo | `HjtDev/django-dynamic-user` |
| Namespacing (`APP-DESIGN.md` §1.2) | settings dict `DYNAMIC_USER`; throttle prefix `dynamic_user_`; cache namespace `dynamic_user`; Celery task names `dynamic_user.tasks.*`; **two** frontend basePath keys — `dynamic_user` → `/api/v1/users` (self-service) and `dynamic_user_admin` → `/api/v1/admin/users` (admin) — this is the first app in the ecosystem with two API surfaces each needing their own basePath, don't collapse them into one |
| Scope | **Data layer only.** No registration, login, JWT, or password reset — those are a separate `auth-app` package's job. This app's public surface for that future app is exactly `get_user_model()` (Django's own indirection) plus whatever `services.py`/`signals.py` this app documents |
| Model strategy | **Swappable concrete defaults**, mirroring `django.contrib.auth` exactly: `AbstractDynamicUser(AbstractBaseUser, PermissionsMixin)`, `AbstractProfile`, `AbstractSetting` as abstract bases; concrete `User`, `Profile`, `Setting` subclassing them with `Meta.swappable = "AUTH_USER_MODEL"` / `"DYNAMIC_USER_PROFILE_MODEL"` / `"DYNAMIC_USER_SETTING_MODEL"` respectively. The two non-user swappable settings are **top-level** Django settings, alongside `AUTH_USER_MODEL` — not keys inside the `DYNAMIC_USER` dict, because Django's `swappable_dependency()` machinery expects a top-level setting name, and mixing the two conventions in one place invites exactly the mistake it's meant to prevent |
| View↔model binding | **Settings-driven field allowlists**, resolved at request time by a serializer factory (`dynamic_user.serializers.build_serializer(model, fields, *, read_only_fields=())`), never a per-host subclass. `DYNAMIC_USER["USER_READ_FIELDS"]`, `["USER_EDITABLE_FIELDS"]`, `["USER_LOCKED_FIELDS"]`, `["PROFILE_EDITABLE_FIELDS"]`, `["PROFILE_PUBLIC_FIELDS"]`, `["SETTING_EDITABLE_FIELDS"]` are the minimum set — Phase 0 finalizes the full list and each one's default |
| Region-specific validators | `DYNAMIC_USER["PHONE_VALIDATORS"]` / `["NAME_VALIDATORS"]` — lists of dotted callable paths, resolved lazily (imported and cached on first use, not at import time of `models.py`) by a single `dynamic_user.validators.run_validators(setting_key, value)` helper every relevant field's `clean`/serializer `validate_*` calls. Default: empty list = no extra validation beyond Django's own field-level checks — this app ships no opinionated phone/name format, only the hook |
| Admin gating | `appkit.permissions.IsAppAdmin` (`is_authenticated and is_staff`) by default on every admin endpoint and the Jazzmin surface — consistent with `cleanup_app` and the rest of the ecosystem. `DYNAMIC_USER["ADMIN_REQUIRES_SUPERUSER"]` (default `False`) tightens every admin gate to `is_superuser` for hosts that want the stricter posture. **Unconditionally, regardless of this setting**: only a request from an actual superuser may write `is_staff`, `is_superuser`, or `is_active` on any user object, including via the admin surface — a staff-only admin can view and edit profile/setting data for anyone but can never escalate anyone's privilege level, itself included |
| Frontend half? | Yes — hooks and managers for **both** surfaces (self-service and admin), sharing `types.ts` |
| User-model need beyond itself | None — this app *is* the user model. `Profile`/`Setting` reference their owning user via `settings.AUTH_USER_MODEL`, same indirection as any other app in the ecosystem would use |
| Other-app references | None beyond `django.contrib.contenttypes`, used only by the optional `History` mixin (a generic per-field change log) — `contenttypes` ships with Django itself, so this isn't an inter-app dependency in the §6 sense |
| `.env` keys | None — this app configures entirely through `DYNAMIC_USER` plus the two top-level swappable-model settings |
| Celery | Optional extra `[celery]`. Tasks: `dynamic_user.tasks.finalize_due_deletions` (turns a past-grace-period `AccountDeletionRequest` into an actual delete/anonymize), `dynamic_user.tasks.purge_deletion_history`. A `process_deletion_requests` management command covers the no-worker host |
| Other extras | `[avatar]` → pulls in `hjtdev-appkit[images]` for `appkit.files.validate_image`, needed only if a host uses the `Avatar` mixin |
| `appkit` helpers used | `permissions.IsAppAdmin`/`IsObjectOwner`, `pagination.DefaultPagination`, `mixins.CachedListMixin`, `cache.build_cache_key`/`cached_call`/`invalidate_namespace`, `throttling.throttle_scope`, `validation.validate_query_params`/`safe_filter_kwargs`/`sanitize_html`, `files.validate_image` (avatar extra only), `media.file_url`, `net.client_ip` (last-seen tracking), `text.to_english_digits` (normalizing Persian-digit phone input before validation), `testing` pytest plugin (`-p appkit.testing`). Frontend: `useApiClient`, `ApiError`/`isApiError`, `mediaUrl`, `toEnglishDigits`. **No gap — no appkit release needed before starting** |
| Coverage gate | 85% (standard app-package bar) |

**Design facts this guide already settled, so no phase re-derives them:**

- The two extra swappable settings resolve exactly like `AUTH_USER_MODEL` does — `apps.py`'s
  `ready()` and a Django system check (`checks.py`) validate both point at an installed,
  migrated, `"app_label.ModelName"`-shaped model that subclasses this app's own abstract base,
  the same way `django.contrib.auth`'s own checks (`auth.E003`, etc.) validate `AUTH_USER_MODEL`.
- `Profile`/`Setting` auto-provisioning (a `post_save` receiver on `User` creating the matching
  row) is **on by default** (`DYNAMIC_USER["AUTO_CREATE_PROFILE"]` /
  `["AUTO_CREATE_SETTING"]`, both `True`) and must use `get_profile_model()`/`get_setting_model()`
  — never the concrete `Profile`/`Setting` — so it keeps working against a host's subclass with
  zero code change.
- `AccountDeletionRequest` references its target user via `settings.AUTH_USER_MODEL` and stores a
  `status` (`pending`/`approved`/`rejected`/`finalized`), `requested_at`, `reviewed_at`,
  `reviewed_by` (nullable FK to `settings.AUTH_USER_MODEL`, `on_delete=SET_NULL`), and
  `finalize_at` (grace-period deadline). "Finalizing" a deletion is `DYNAMIC_USER["DELETION_MODE"]`-
  driven: `"hard_delete"` (default) or `"anonymize"` (host-configurable field-scrub function).

---

## 2. The build, phase by phase

Fresh session per phase, same hygiene as always: `/clear` between phases, one phase's scope only,
review every diff, verification command's real output pasted before moving on.

### Phase 0 — The contract (no code)

```
Phase 0: design the public contract. Write it to docs/CONTRACT.md. No implementation code.

Read docs/APP-DESIGN.md fully first — especially §1 (package contract), §2's "Referencing the
host's user model" note, §6 (inter-app communication), and §8 (README contract). Also read
docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md §0 and §1 in full — this app's name, module, scope
(data layer only, no auth), model-swapping strategy, settings-driven serializer approach, and
every namespacing decision are already made there; do not re-derive or change them, only
formalize them into CONTRACT.md's required shape. Flag, rather than silently resolve, anything
that seems to need a decision §1 didn't make.

This is django-dynamic-user (module: dynamic_user) — the swappable User/Profile/Setting layer for
a host project. It ships abstract + concrete swappable models, self-service and admin DRF
surfaces, a Jazzmin admin, an opt-out account-deletion review flow, a small mixin library, and a
settings-driven serializer factory so a host that subclasses any of the three models never has to
touch this package's views. It does not do registration, login, JWT, or password reset.

Produce, using the specifics below as the starting point — refine names/shapes only where the
reasoning is genuinely better, and flag any change explicitly rather than silently drifting:

1. Models — full field lists, types, indexes, every FK:
   - AbstractDynamicUser(AbstractBaseUser, PermissionsMixin) — username (unique), name, email
     (unique), phone (unique, nullable — not every host requires it), is_active, is_staff,
     is_superuser, date_joined. USERNAME_FIELD and REQUIRED_FIELDS as class attributes (flag this
     as the one deliberate exception to "no settings-affecting class attribute," per §0 item 2).
     A concrete User(AbstractDynamicUser) with Meta.swappable = "AUTH_USER_MODEL".
   - AbstractProfile — user (OneToOneField to settings.AUTH_USER_MODEL, related_name="profile"),
     bio, avatar-related fields IF the Avatar mixin composes rather than duplicates them (decide
     which and document it), is_public (bool, default True — gates the public-profile endpoint).
     Concrete Profile(AbstractProfile) with Meta.swappable = "DYNAMIC_USER_PROFILE_MODEL".
   - AbstractSetting — user (OneToOneField, related_name="setting"), a small starter set of
     genuinely generic preferences (e.g. language, timezone, notifications_enabled) — keep this
     minimal, a host's own subclass is where project-specific settings go. Concrete
     Setting(AbstractSetting) with Meta.swappable = "DYNAMIC_USER_SETTING_MODEL".
   - AccountDeletionRequest — user (FK, CASCADE), status, requested_at, reviewed_at, reviewed_by
     (nullable FK to settings.AUTH_USER_MODEL, SET_NULL), finalize_at, reason (optional
     TextField). Index on (status, finalize_at) for the task/command that scans for due rows.
   - Mixins (models.py or a dedicated mixins.py — decide and document): AvatarMixin, TimestampMixin,
     HistoryMixin (contenttypes-based generic change log — the one place contenttypes is used),
     SoftDeleteMixin, VerificationMixin (email/phone verified flags + timestamps, no delivery
     logic — sending the verification code is an auth-app's or host's job), LastSeenMixin,
     MetadataMixin (a JSONField escape hatch). Full field lists for each.
   Every FK-shaped reference to a user must be settings.AUTH_USER_MODEL. Flag anything that would
   need a concrete import instead.

2. Resolution — dynamic_user.resolution: get_profile_model() -> type[Model], get_setting_model()
   -> type[Model], get_profile_model_string() -> str, get_setting_model_string() -> str, mirroring
   django.contrib.auth.get_user_model()'s own caching/error-message conventions (raise
   ImproperlyConfigured with a message naming the misconfigured setting, not a generic
   AttributeError).

3. Signals — name + exact payload kwargs + when it fires. Minimum set: user_registered_profile_
   created is wrong (registration isn't this app's job) — instead: profile_created,
   setting_created (both: user_id), deletion_requested (user_id, request_id, finalize_at),
   deletion_reviewed (request_id, status, reviewed_by_id), deletion_finalized (user_id, mode),
   profile_updated (user_id, changed_fields: list[str]) — argue for the minimum viable payload on
   each per the versioned-contract rule; a host's future auth-app or notification-app hooks these.

4. services.py — full signatures, fully typed. Minimum set: ProfileService.update(user,
   validated_data) -> Profile, SettingService.update(user, validated_data) -> Setting,
   DeletionService.request(user, *, reason="") -> AccountDeletionRequest,
   DeletionService.review(request_id, *, approved, reviewed_by) -> AccountDeletionRequest,
   DeletionService.finalize(request_id) -> None, DeletionService.cancel(user) -> None.

5. Endpoints — both surfaces, every one: method, path, permission, throttle scope name
   (dynamic_user_/dynamic_user_admin_ prefixed), request/response shape.
   User-facing (urls.py): GET /me/ (locked fields included, read-only), GET+PATCH /me/profile/,
   GET+PATCH /me/setting/, GET /profiles/ (paginated, public only), GET /profiles/{id}/ (public
   fields only, 404 if is_public=False and requester isn't the owner), POST /me/deletion-request/,
   GET /me/deletion-request/ (current status), DELETE /me/deletion-request/ (cancel while pending).
   Admin (urls_admin.py): GET /users/ (paginated, filterable), GET/PATCH /users/{id}/ (PATCH
   restricted per §0 item 3's superuser-only fields — spell out exactly which serializer fields
   are gated behind the extra check), GET/PATCH /users/{id}/profile/, GET/PATCH
   /users/{id}/setting/, GET /deletion-requests/ (paginated, filterable by status), POST
   /deletion-requests/{id}/review/ (approve/reject), POST /deletion-requests/{id}/finalize/ (force,
   bypassing finalize_at — document why this is safe or restrict it further).

6. Settings dict DYNAMIC_USER with every DEFAULTS key from §1 above (field allowlists, validator
   lists, ADMIN_REQUIRES_SUPERUSER, AUTO_CREATE_PROFILE, AUTO_CREATE_SETTING, DELETION_MODE,
   DELETION_GRACE_PERIOD_DAYS, and anything else this phase's design surfaces), plus the two
   top-level swappable-model settings (documented separately, since they're not DYNAMIC_USER keys).
   Explain every key and any interaction between them (e.g. a field appearing in
   PROFILE_PUBLIC_FIELDS but not existing on a host's subclassed model must degrade gracefully,
   not 500 — state the exact resolution rule).

7. Frontend hooks — both surfaces. Self-service: useMe(), useMyProfile(), useUpdateMyProfile(),
   useMySetting(), useUpdateMySetting(), usePublicProfiles(params), usePublicProfile(id),
   useMyDeletionRequest(), useRequestDeletion(), useCancelDeletionRequest(). Admin: useAdminUsers
   (params), useAdminUser(id), useUpdateAdminUser(id), useAdminUserProfile(id),
   useAdminUserSetting(id), useAdminDeletionRequests(params), useReviewDeletionRequest(),
   useFinalizeDeletionRequest(). Name + what each wraps + query key + invalidation behavior for
   every one — this is a long list, be exhaustive rather than "and so on."

8. tasks.py — dynamic_user.tasks.finalize_due_deletions (scans AccountDeletionRequest where
   status="approved" and finalize_at <= now, calls DeletionService.finalize), and
   dynamic_user.tasks.purge_deletion_history. Behind the celery extra only. Recommended schedule
   for each.

9. Dependencies: "hjtdev-appkit>=2.0,<3.0" in [project.dependencies]; "celery[redis]>=5.4,<6.0"
   as the "celery" extra; "hjtdev-appkit[images]" (or however appkit's own extras compose) as the
   "avatar" extra — verify against appkit's actual extras table rather than assuming. Call out
   anything a host is also likely to depend on directly.

For each of 1–8: state explicitly whether it requires knowledge of another app package. It never
should, beyond django.contrib.contenttypes (stdlib-equivalent, ships with Django) for
HistoryMixin — if anything else seems to, propose the decoupled alternative rather than accepting
it.
```

**Review this yourself before Phase 1.** Beyond the generic guide's four checks: does every
signal payload stay a bare ID/primitive rather than a model instance (a host receiver shouldn't
need this app's models imported to log the event)? Does the `PATCH /users/{id}/` admin endpoint's
contract make the superuser-only field gate explicit enough that Phase 6 can't accidentally
implement it as "any staff user can PATCH anything"? Does `PROFILE_PUBLIC_FIELDS`' default list
contain zero fields that could plausibly be sensitive (real name might be fine, phone/email are
not) — this default ships into every host that doesn't override it.

### Phase 1 — Package skeleton, `pyproject.toml`, boundary enforcement

```
Phase 1: the package skeleton. docs/APP-DESIGN.md §2 and §3, this app's docs/CONTRACT.md.

Create the repo structure from APP-DESIGN.md §2 exactly (module directory is dynamic_user), then:
1. backend/pyproject.toml complete per §3.1 — dependencies from CONTRACT.md item 9 with WIDE
   RANGES: "django>=5.2,<7.0", "djangorestframework>=3.15,<4.0", "drf-spectacular>=0.27,<1.0",
   "hjtdev-appkit>=2.0,<3.0". [project.optional-dependencies]: celery = ["celery[redis]>=5.4,<6.0",
   "django-celery-beat>=2.7,<3.0"], avatar = ["hjtdev-appkit[images]>=2.0,<3.0"] (confirm this is
   how appkit's own extra is actually named before committing to it — check appkit's README/
   pyproject, don't guess). [dependency-groups] dev + test per §3.1's template. [tool.uv]
   default-groups = ["dev", "test"]. Coverage threshold 85 in addopts. Wire "-p appkit.testing"
   into [tool.pytest.ini_options] addopts.
2. The flake8-tidy-imports banned-api block: list every OTHER app package in the ecosystem
   (currently just "cleanup_app" — ask if unsure whether more exist by the time you run this),
   plus "dynamic_user.factories" test-only guard. Do NOT add lines for "appkit" or
   "django.contrib.contenttypes" — the first is a declared dependency, the second ships with
   Django itself.
3. backend/MANIFEST.in so locale/, templates/, and static/ ship in the wheel.
4. .python-version (3.14), .gitignore, .pre-commit-config.yaml per §3.6.
5. src/dynamic_user/__init__.py, apps.py — AppConfig with a translatable verbose_name and a
   ready() that (a) imports and connects the profile/setting auto-provisioning receivers from
   signals.py when conf.get_setting("AUTO_CREATE_PROFILE")/("AUTO_CREATE_SETTING") are true
   (default true), and (b) registers this app's Django system checks (see conf.py note below).
   conf.py per §3.5 with the DEFAULTS from CONTRACT.md item 6.
6. checks.py — Django system checks (registered from apps.py's ready(), per Django's
   django.core.checks framework) validating: DYNAMIC_USER_PROFILE_MODEL and
   DYNAMIC_USER_SETTING_MODEL are both set and both resolve to an installed, "app_label.Model"-
   shaped model subclassing this app's own AbstractProfile/AbstractSetting — mirror the shape and
   error-code style of django.contrib.auth's own AUTH_USER_MODEL checks. These must not crash at
   import time on a fresh, unconfigured host — a missing setting is a check *warning/error* at
   Django startup, never an ImportError while collecting apps.py itself.
7. resolution.py per CONTRACT.md item 2 — get_profile_model(), get_setting_model(), and the two
   *_model_string() variants, with Django's own apps.get_model() + a small cache, invalidated the
   same way django.contrib.auth.get_user_model() itself handles it (safe under Django's app
   registry lifecycle — do not hand-roll a naive module-level cache that survives test-database
   teardown/rebuild incorrectly).
8. Empty-but-present, each with a docstring stating its role per CONTRACT.md: models.py,
   managers.py, mixins.py, validators.py, views.py, views_admin.py, serializers.py,
   permissions.py, signals.py, services.py, urls.py, urls_admin.py, admin.py, admin_views.py,
   tasks.py, factories.py. utils.py only if a genuine private helper turns up with nowhere else
   to go.

Run `uv sync`, then `uv sync --extra celery`, then `uv sync --extra avatar`, then `uv build`.
Paste all four outputs.
```

**Verify:** all four commands succeed; `dependencies` are ranges, not `==`, including on
`appkit`; `checks.py` genuinely does not crash a fresh, zero-config Django project at
`manage.py check` time (an unset `DYNAMIC_USER_PROFILE_MODEL` should print a system-check error
naming the setting, not a traceback).

**Review for:** exact pins anywhere; `include-package-data` present; `banned-api` populated and
**not** listing `appkit` or `contenttypes`; the `avatar` extra's dependency string actually matches
what appkit publishes (don't invent an extra name appkit doesn't have — verify against appkit's
own `pyproject.toml`/README before trusting this guide's guess).

### Phase 2 — Models, mixins, validators, migrations

The phase where the swappable-model machinery either works or doesn't. Read `APP-DESIGN.md` §2's
"Referencing the host's user model" note twice before writing `models.py`.

```
Phase 2: data layer. docs/APP-DESIGN.md §2, this app's docs/CONTRACT.md item 1, and
docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md §0 items 1 and 2 — read both before writing a single
model field.

Implement models.py exactly as CONTRACT.md specifies:
- AbstractDynamicUser(AbstractBaseUser, PermissionsMixin) + concrete User with
  Meta.swappable = "AUTH_USER_MODEL". USERNAME_FIELD/REQUIRED_FIELDS as class attributes — this
  is the one sanctioned exception to "nothing settings-driven lives on the class," say so in a
  docstring.
- AbstractProfile + concrete Profile, AbstractSetting + concrete Setting, each with
  Meta.swappable set to this app's own top-level setting name (never AUTH_USER_MODEL's name —
  that would be a straight collision) and a OneToOneField to settings.AUTH_USER_MODEL.
- AccountDeletionRequest exactly as specified — FK to settings.AUTH_USER_MODEL for both `user`
  and `reviewed_by` (SET_NULL on the latter), Meta.indexes on (status, finalize_at).
- Meta.indexes for every field used in filters/ordering across the whole models.py.
- Zero imports of a concrete User/Profile/Setting from anywhere else in this file or any other —
  even AccountDeletionRequest's FK uses settings.AUTH_USER_MODEL, not User directly, despite
  living in the same models.py as User's own definition.

mixins.py — AvatarMixin, TimestampMixin, HistoryMixin, SoftDeleteMixin, VerificationMixin,
LastSeenMixin, MetadataMixin, each a small, composable abstract model per CONTRACT.md item 1.
HistoryMixin is the only one touching contenttypes — a GenericForeignKey-based change-log row
model, with a manager method logging a diff. Document, in each mixin's docstring, exactly which
fields it adds and any Meta it requires the composing model to also set (e.g. HistoryMixin needing
its own log model registered).

validators.py — run_validators(setting_key: str, value: Any) -> None, resolving
conf.get_setting(setting_key) as a list of dotted paths, importing and calling each lazily
(cache the imported callables, never re-import per call, but never at models.py import time
either — the import must happen no earlier than first actual validation call, so a host can
change the setting without restarting anything import-order-sensitive). Raise
django.core.exceptions.ValidationError on failure, matching Django's own validator-raising
convention so DRF's serializer layer surfaces it the normal way.

Then makemigrations, and verify 0001_initial uses
migrations.swappable_dependency(settings.AUTH_USER_MODEL) for every FK/O2O to the user, and that
Profile/Setting's own migrations are structured so a host CAN point
DYNAMIC_USER_PROFILE_MODEL/DYNAMIC_USER_SETTING_MODEL at a swapped-in model the same way
AUTH_USER_MODEL itself supports swapping — add migrations.swappable_dependency for those two
settings as well, even though they're not Django's own AUTH_USER_MODEL (this is what makes the
resolution.py machinery from Phase 1 actually safe to point at a subclass).

Then admin.py: ModelAdmin for User (list_display incl. username, email, is_staff, is_active;
list_filter on is_staff/is_active; NEVER expose password as anything but the standard
change-password link Django's own UserAdmin uses — subclass django.contrib.auth.admin.UserAdmin's
pattern, don't reinvent it), Profile, Setting, AccountDeletionRequest (list_filter on status,
readonly on requested_at/reviewed_at, an admin action for approve/reject calling
DeletionService.review — never a raw queryset .update()). select_related/prefetch_related on
every get_queryset. Do NOT touch JAZZMIN_SETTINGS — note suggested icons for the README instead.

Create tests/backend/settings.py per APP-DESIGN.md §7.1 — Postgres, dynamic_user in
INSTALLED_APPS, AUTH_USER_MODEL = "dynamic_user.User", DYNAMIC_USER_PROFILE_MODEL =
"dynamic_user.Profile", DYNAMIC_USER_SETTING_MODEL = "dynamic_user.Setting" — then run `uv run
pytest --create-db` to prove migrations apply from zero. Paste the output.

Also add a SECOND settings module, tests/backend/settings_swapped.py, importing everything from
settings.py but pointing AUTH_USER_MODEL/DYNAMIC_USER_PROFILE_MODEL/DYNAMIC_USER_SETTING_MODEL at
a tiny host-style app under tests/backend/swapped_app/ that subclasses all three abstract bases
with one extra field each. Run `DJANGO_SETTINGS_MODULE=tests.backend.settings_swapped uv run
pytest --create-db -k swapped` (a handful of smoke tests referencing this settings module) to
prove the swap machinery works from Phase 2 onward, not just once Phase 4's serializer factory
exists. Paste that output too.
```

**Verify:** both settings modules' migrations apply against real Postgres from zero;
`swappable_dependency` present for all three swappable settings, not just `AUTH_USER_MODEL`; the
swapped-model smoke test passes.

**Review for:** any concrete `User`/`Profile`/`Setting` import anywhere, including inside
`admin.py` or a mixin; missing indexes; a validator resolved eagerly at import time instead of
lazily; `HistoryMixin` reaching for anything beyond `contenttypes`.

### Phase 3 — Resolution, services, signals, auto-provisioning, tasks

```
Phase 3: business logic. docs/APP-DESIGN.md §6, this app's docs/CONTRACT.md items 2, 3, 4, 8, and
docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md §0 item 1.

Implement:
- resolution.py — finish per Phase 1's stub if anything was left incomplete; this is the single
  place every other file in this package calls through to reach Profile/Setting.
- signals.py — every signal from CONTRACT.md item 3, each with a comment documenting its exact
  payload above it, matching CONTRACT.md character for character. Payloads carry IDs and
  primitives only — never a model instance, so a host receiver never needs this app's models
  imported just to read an event.
- A receiver connected in apps.py's ready() (Phase 1) implementing profile/setting
  auto-provisioning: on User post_save (created=True), call get_profile_model().objects.
  get_or_create(user=instance) and the Setting equivalent, gated individually by
  conf.get_setting("AUTO_CREATE_PROFILE")/("AUTO_CREATE_SETTING"), then send profile_created/
  setting_created. Must use the resolved model, never a concrete import — this is the mixin/
  swap machinery's first real exercise.
- services.py — ProfileService, SettingService, DeletionService exactly per CONTRACT.md item 4,
  fully typed. DeletionService.request() computes finalize_at from
  conf.get_setting("DELETION_GRACE_PERIOD_DAYS"), sets status="pending", sends
  deletion_requested. .review() moves pending -> approved/rejected, stamps reviewed_at/
  reviewed_by, sends deletion_reviewed; rejecting a request is terminal, approving schedules it
  for finalize_at. .finalize() implements DYNAMIC_USER["DELETION_MODE"] — "hard_delete" deletes
  the user row (cascade takes Profile/Setting/AccountDeletionRequest's own FKs per each model's
  on_delete), "anonymize" calls a conf-resolved anonymize function instead of deleting — sends
  deletion_finalized either way, with mode in the payload. .cancel() only works while
  status="pending".
- tasks.py — dynamic_user.tasks.finalize_due_deletions (queries AccountDeletionRequest where
  status="approved" and finalize_at<=now, calls DeletionService.finalize per row, continues past
  a single row's failure rather than aborting the batch) and
  dynamic_user.tasks.purge_deletion_history. Behind the celery extra only.
- management/commands/process_deletion_requests.py — thin wrapper around
  finalize_due_deletions's own logic (call the same underlying function, don't duplicate it), for
  a host with no Celery worker.

Hard constraints, restated because this is the phase they matter most:
- No import of any other app package. appkit and contenttypes ARE allowed (declared dependency /
  ships with Django).
- No import from a host (core, tools, config).
- Zero direct references to concrete User/Profile/Setting anywhere in this file's own code —
  everything reaching Profile/Setting goes through resolution.py, and everything reaching the
  user goes through settings.AUTH_USER_MODEL or the instance already in hand.
- Every service method emitting a signal emits EXACTLY the documented payload.
- Anything configurable comes from conf.get_setting(), never a hardcoded literal.

Then write tests: happy path + at least one failure path per service method; one test per signal
asserting the exact payload by connecting a receiver; a test proving auto-provisioning creates
Profile/Setting rows through the SWAPPED settings module from Phase 2 (not just the default one);
a test proving DELETION_MODE="anonymize" never issues a DELETE query; a test proving .finalize()
on a non-"approved" request raises rather than silently no-op-ing. Run pytest against BOTH
settings modules.
```

**Verify:** `uv run pytest` green against both `tests.backend.settings` and
`tests.backend.settings_swapped`; `uv run ruff check .` clean.

**Review for:** signal payloads matching `CONTRACT.md` exactly; any hardcoded value that should
be a setting; **any place resolution.py was bypassed** — this is the single most important review
in this phase, since it's the mechanism the entire package's value proposition depends on;
`finalize_due_deletions` aborting the whole batch on one row's exception.

### Phase 4 — The serializer factory

Its own phase because it's the load-bearing mechanism the "hard part" you called out lives in —
get this wrong and every host that subclasses a model has a broken PATCH endpoint no amount of
view-layer code can fix.

```
Phase 4: the settings-driven serializer factory. docs/APP-DESIGN.md §4, this app's
docs/CONTRACT.md's settings-driven-binding decision (§1 of
docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md).

Implement serializers.py's core: build_serializer(model: type[Model], fields: Sequence[str], *,
read_only_fields: Sequence[str] = (), extra_kwargs: dict | None = None) -> type[ModelSerializer].
Requirements:
- Built once per (model, fields, read_only_fields) combination and cached (functools.lru_cache or
  equivalent, keyed on a hashable form of the arguments) — NOT rebuilt on every request, since
  drf-spectacular introspects the class object itself and a fresh class per request breaks
  schema generation's ability to name it stably.
- fields is validated against model._meta.get_fields() at build time — a name in a settings list
  that doesn't exist on the RESOLVED model (get_profile_model(), not a hardcoded Profile) raises
  ImproperlyConfigured with a message naming the offending field and setting key, at server
  startup or first use, never a silent drop and never a 500 mid-request.
- Never emits password, or any field whose internal Django field type is a password hasher's
  target — build_serializer takes an explicit deny-list constant (["password"]) it refuses to
  include even if a caller's fields list names it, and raises loudly if asked to.
- Read-only construction (e.g. for GET /me/) vs. writable construction (PATCH) are two distinct
  calls into this same factory with different `fields`/`read_only_fields`, not two code paths —
  demonstrate both.

Wire actual usage: a serializers.py module level that calls build_serializer() against
resolution.get_profile_model() etc. for USER_READ_FIELDS/USER_EDITABLE_FIELDS/
PROFILE_EDITABLE_FIELDS/PROFILE_PUBLIC_FIELDS/SETTING_EDITABLE_FIELDS from conf.get_setting(),
producing the concrete serializer classes Phase 5/6's views import.

Then tests, run against BOTH tests.backend.settings and tests.backend.settings_swapped:
- A serializer built for the swapped Profile subclass (which has one extra field per Phase 2's
  swapped_app) actually includes that extra field when it's added to
  DYNAMIC_USER["PROFILE_EDITABLE_FIELDS"] in settings_swapped.py — and a full PATCH round-trip
  through this serializer (not just instantiation) sets it correctly.
- A field name in a settings list that doesn't exist on the model raises ImproperlyConfigured at
  build time, with a message naming the field.
- password is refused even when explicitly requested.
- Building the same (model, fields) twice returns the cached class, not two distinct types
  (assert `is`, not just `==`) — this is what makes drf-spectacular schema generation stable
  across requests.

Run pytest, paste output including the swapped-settings run.
```

**Verify:** the round-trip-through-a-subclassed-model test passes against
`tests.backend.settings_swapped`; the cache-identity test passes.

**Review for:** any place a serializer is built inline in a view instead of through
`build_serializer` (defeats the caching and the field-existence guard); `password` sneaking
through via a field alias or a `source=` trick; the factory reaching for a concrete model instead
of calling `resolution.py`.

### Phase 5 — Self-service API

```
Phase 5: the user-facing API. docs/APP-DESIGN.md §4, this app's docs/CONTRACT.md item 5's
user-facing half.

Implement serializers.py's remaining pieces, permissions.py, views.py, urls.py.

permissions.py exposes at minimum: IsProfileOwner (object-level — a user may only write their own
Profile/Setting, checked against request.user, not trusted from the URL), IsPublicOrOwner (for
GET /profiles/{id}/ — allow if profile.is_public or requester is the owner, 404 rather than 403
for a private profile someone else requests, so existence isn't leaked). Prefer importing
appkit.permissions.IsObjectOwner as a base where its owner_field="user" shape already covers the
need; only write new logic for what it doesn't.

Every view in views.py, without exception:
- a namespaced throttle_scope: dynamic_user_me, dynamic_user_profile_update,
  dynamic_user_setting_update, dynamic_user_profiles_list, dynamic_user_profile_retrieve,
  dynamic_user_deletion_request.
- a complete @extend_schema: summary, description, request/response serializers,
  tags=["dynamic-user"].
- GET /me/: the USER_READ_FIELDS serializer from Phase 4, IsAuthenticated, no locked field
  ever writable from this or any other user-facing view.
- GET+PATCH /me/profile/, GET+PATCH /me/setting/: PATCH uses the *_EDITABLE_FIELDS serializer,
  IsAuthenticated + IsProfileOwner (object resolved from request.user, never a URL-supplied ID —
  there is no "edit someone else's profile" shape on this surface at all).
- GET /profiles/ (appkit.pagination.DefaultPagination, appkit.mixins.CachedListMixin,
  cache_namespace="dynamic_user"): queryset filtered to is_public=True, PROFILE_PUBLIC_FIELDS
  serializer only.
- GET /profiles/{id}/: PROFILE_PUBLIC_FIELDS serializer, IsPublicOrOwner, 404 (not 403) when
  private and requester isn't the owner.
- POST /me/deletion-request/, GET /me/deletion-request/, DELETE /me/deletion-request/: calling
  DeletionService directly, never touching the model layer themselves. POST 409s (not 500) if a
  pending/approved request already exists rather than creating a duplicate.

Write serializers with explicit field lists throughout (the factory already enforces this, but
any hand-written serializer in this phase — e.g. the deletion-request request/response shape,
which isn't a settings-driven model surface — follows the same rule). Never expose password,
is_staff, is_superuser, or reviewed_by on any user-facing serializer.

Then tests, run against BOTH settings modules: every view gets 200 for the permitted user, 403 (or
404 where specified) for another user's object, 401 unauthenticated. A test that PATCH /me/ (if it
existed) or any attempt to write a locked field via /me/profile/ or /me/setting/ is rejected. A
test that a private profile 404s for a non-owner and 200s for the owner. A test that POST
/me/deletion-request/ twice returns 409 the second time. One test per throttle scope. Run pytest
and paste coverage.

Then generate the schema: DJANGO_SETTINGS_MODULE=tests.backend.settings uv run python manage.py
spectacular --file schema.yml --fail-on-warn, and commit schema.yml.
```

**Verify:** coverage over 85%; the private-profile-404 test exists and genuinely fails if
`IsPublicOrOwner` is swapped for a permission that only checks authentication;
`--fail-on-warn` clean.

**Review for:** any view resolving its target object from a URL-supplied ID instead of
`request.user` on the self-service surface (that would be the admin surface's shape leaking in
here); a locked field reachable through any self-service PATCH; a public list/retrieve view
returning anything outside `PROFILE_PUBLIC_FIELDS`.

### Phase 6 — Admin API and Jazzmin admin

The privilege-escalation phase. Read `docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md` §0 item 3 twice.

```
Phase 6: the admin surface — both the DRF admin API and the Jazzmin ModelAdmin registrations
(the latter was stubbed with real ModelAdmin classes back in Phase 2; this phase is about the
custom admin_views.py API and any Jazzmin admin action Phase 2 deferred). docs/APP-DESIGN.md §5,
this app's docs/CONTRACT.md item 5's admin half, and
docs/CLAUDE-CODE-GUIDE-APP-DYNAMIC-USER.md §0 item 3.

permissions.py adds: an admin gate resolving conf.get_setting("ADMIN_REQUIRES_SUPERUSER") — False
(default) uses appkit.permissions.IsAppAdmin (is_staff) as-is; True swaps in an equivalent
is_superuser check. Build this as one callable/class the rest of this phase imports, not a
conditional repeated at every view. Separately, and NOT gated by that setting at all:
CanEscalatePrivilege (or equivalent) — only request.user.is_superuser may proceed when the
request body touches is_staff, is_superuser, or is_active on the target user. This check runs
even when the general admin gate above resolved to "staff is enough."

Every view in admin_views.py, without exception:
- the admin gate above (never appkit.permissions.IsAppAdmin directly if
  ADMIN_REQUIRES_SUPERUSER support is meant to apply here — route through this app's own wrapper).
- a namespaced throttle_scope: dynamic_user_admin_users_list, dynamic_user_admin_user_retrieve,
  dynamic_user_admin_user_update, dynamic_user_admin_profile_update,
  dynamic_user_admin_setting_update, dynamic_user_admin_deletions_list,
  dynamic_user_admin_deletion_review, dynamic_user_admin_deletion_finalize.
- a complete @extend_schema, tags=["dynamic-user-admin"].
- GET /users/: paginated (appkit.pagination.DefaultPagination), filterable via
  appkit.validation.validate_query_params + safe_filter_kwargs (never raw **request.GET into a
  filter() call).
- GET/PATCH /users/{id}/: PATCH runs the CanEscalatePrivilege check BEFORE touching is_staff/
  is_superuser/is_active — reject the whole request (400/403, your call, document which) rather
  than silently dropping just those fields, so a caller gets an honest error instead of a
  request that appeared to succeed but didn't do what was asked.
- GET/PATCH /users/{id}/profile/, GET/PATCH /users/{id}/setting/: admin can read/write EVERY
  field (not just *_PUBLIC_FIELDS/*_EDITABLE_FIELDS) — use a full-fields build_serializer() call
  here, still going through the Phase 4 factory, still excluding password globally.
- GET /deletion-requests/ (filterable by status), POST /deletion-requests/{id}/review/ (body:
  approved: bool, calls DeletionService.review(reviewed_by=request.user)), POST
  /deletion-requests/{id}/finalize/ (calls DeletionService.finalize() early, bypassing
  finalize_at — restrict this to superuser regardless of ADMIN_REQUIRES_SUPERUSER, since it's a
  genuinely irreversible action a staff-level admin dashboard shouldn't be able to trigger by
  accident).

Then tests, against both settings modules: every admin view 403s a non-admin per
ADMIN_REQUIRES_SUPERUSER=False (staff-not-superuser allowed) AND =True (staff-not-superuser now
403s) — two full passes, not one. A dedicated privilege-escalation test: a staff (non-superuser)
admin PATCHing is_staff/is_superuser/is_active on ANY user, including themselves, is rejected,
proven by actually attempting it, not by reading the permission class. A test that
/deletion-requests/{id}/finalize/ 403s a plain staff admin. Run pytest, paste coverage.

Regenerate schema.yml (same command as Phase 5) now that both surfaces exist; commit it.
```

**Verify:** the two full ADMIN_REQUIRES_SUPERUSER passes both green; the privilege-escalation
test exists and genuinely fails if `CanEscalatePrivilege` is temporarily removed — try it.

**Review for:** any admin PATCH path that reaches `is_staff`/`is_superuser`/`is_active` without
going through `CanEscalatePrivilege` first; `/deletion-requests/{id}/finalize/` reachable by a
non-superuser; the Jazzmin admin's own approve/reject action (Phase 2) bypassing
`DeletionService` and mutating the row directly.

### Phase 6.5 — i18n retrofit (fa locale)

Not part of the original phase sequence — added after Phase 6 shipped, once it became clear
`locale/` held only a `.gitkeep` despite the Makefile's `messages`/`compilemessages` targets
already assuming a real catalog, and `apps.py`'s `verbose_name` was the only translatable string
in the whole package.

```
i18n retrofit: translate the Django-admin-facing surface into fa, matching cleanup_app's own
precedent exactly (the only other app in this ecosystem shipping a locale/fa) — NOT a new
convention. Read cleanup_app/backend/src/cleanup_app/{models,admin}.py first for the shape to
mirror.

In scope: models.py (verbose_name on every field this package itself defines, help_text only
where the field's purpose isn't obvious from its name, Meta.verbose_name/verbose_name_plural on
every model, AccountDeletionRequest.Status's four TextChoices members getting real _() labels),
mixins.py (same, for every field-bearing mixin), admin.py (the two @admin.action descriptions,
and _review_selected's three messages.* calls restructured through
django.utils.translation.ngettext for the two count-bearing ones).

Explicitly out of scope, matching cleanup_app: services.py, views.py, admin_views.py,
permissions.py, checks.py, validators.py — DRF/API-layer strings stay in English. Do not
translate DeletionRequestAlreadyExists/InvalidDeletionState, CanEscalatePrivilege's denial
message, or any system-check Error() message without a deliberate, separately-confirmed decision
to break from that precedent.

Migration handling: verbose_name/help_text/TextChoices labels are part of Django's migration
state. Run `makemigrations --check --dry-run -v3` against every settings module that has its own
migrated app subclassing these abstract bases (tests.backend.settings for dynamic_user itself +
mixin_app's Widget, tests.backend.settings_swapped for swapped_app, settings_partial_swap for
partial_app, settings_user_swap for user_swap_app) — each will report a real, tool-generated diff
the first time. Amend each app's already-merged 0001_initial.py in place using that diff as the
literal source of truth for field kwargs (never guessed by hand), rather than adding a
0002_alter_*.py — safe only pre-v1.0.0, before any tagged release/real host has migrated against
it. Re-run --check --dry-run after each amend until every settings module reports "No changes
detected".

Then: `make messages` to regenerate the .po skeleton from source (real #: file:line references,
correct POT-Creation-Date — never hand-write these), fill every msgstr with Persian translations,
`make compilemessages` (msgfmt --check). Two tests in test_admin.py, mirroring
cleanup_app/tests/backend/test_admin_orphans.py's own locale section: the compiled .mo exists and
is non-empty, and translation.override("fa") + translation.gettext(...) round-trips at least one
model-label string and one admin-action-description string.

Run pytest against every settings module, paste coverage. Run make lint/typecheck.
```

**Verify:** `makemigrations --check --dry-run` reports no changes under every settings module
listed above; both locale tests pass; `make test`'s coverage gate still clears 85%.

**Review for:** any DRF/API-layer string (services.py/views.py/admin_views.py/permissions.py)
accidentally wrapped in `gettext_lazy` — that would silently expand this unit's scope beyond the
cleanup_app precedent it's supposed to match; a migration file edited by hand that doesn't
actually match `makemigrations --check --dry-run`'s real diff.

### Phase 7 — Frontend SDK

```
Phase 7: the frontend half. docs/APP-DESIGN.md §12, this app's docs/CONTRACT.md item 7.

Create in frontend/:
- package.json: name "@hjtdev/django-dynamic-user", react/@tanstack/react-query/@hjtdev/appkit as
  peerDependencies ONLY, openapi-typescript as devDependency, generate:types script
  ("openapi-typescript ../backend/schema.yml -o src/schema.d.ts"), exports map with just ".",
  files: ["dist"], version matching backend/pyproject.toml.
- Run npm run generate:types -> src/schema.d.ts. Never hand-edit it.
- tsconfig.json (strict), tsconfig.build.json, vitest.config.ts, eslint config.
- src/types.ts — re-export narrowed aliases from schema.d.ts (User, Profile, Setting,
  PublicProfile, AccountDeletionRequest, etc.), re-export HttpClient from @hjtdev/appkit.
- src/api/config.ts: TWO config hooks, one per surface — export const useDynamicUserConfig =
  () => useApiClient("dynamic_user", "/api/v1/users"); export const
  useDynamicUserAdminConfig = () => useApiClient("dynamic_user_admin", "/api/v1/admin/users");
  — neither exported from index.ts.
- src/api/manager.ts — TWO managers: DynamicUserManager (self-service: getMe, getMyProfile,
  updateMyProfile, getMySetting, updateMySetting, listPublicProfiles(params),
  getPublicProfile(id), getMyDeletionRequest, requestDeletion, cancelDeletionRequest) and
  DynamicUserAdminManager (listUsers(params), getUser(id), updateUser(id, data),
  getUserProfile(id), updateUserProfile(id, data), getUserSetting(id), updateUserSetting(id,
  data), listDeletionRequests(params), reviewDeletionRequest(id, approved),
  finalizeDeletionRequest(id)). Both instance-based, constructor takes client + basePath. Neither
  exported from index.ts.
- src/hooks/ — every hook from CONTRACT.md item 7, thin react-query wrappers reading the
  appropriate config hook, building the appropriate manager with useMemo. Export
  dynamicUserKeys (self-service) and dynamicUserAdminKeys (admin) factories, kept as two
  separate factories under one shared "dynamic_user"/"dynamic_user_admin" root each — a mutation
  invalidates only its own surface's keys unless CONTRACT.md documents a genuine cross-surface
  invalidation (e.g. an admin PATCH to a user's profile probably shouldn't silently invalidate
  the SELF-SERVICE cache of some other logged-in session — decide and document, don't default to
  invalidating everything).
- src/index.ts — hooks, both key factories, and this app's own types only. No provider, no
  manager, no config hook exported.

Then tests/frontend with Vitest + MSW: success AND error path per hook, onUnhandledRequest:
"error", retry: false. Wrap renders in appkit's ApiClientProvider configured with BOTH basePaths
("dynamic_user" and "dynamic_user_admin") and a stub client. A test proving
useUpdateAdminUser/useReviewDeletionRequest/useFinalizeDeletionRequest/useRequestDeletion/
useCancelDeletionRequest only fire on an explicit mutate() call, never on mount — several of
these are irreversible per APP-DESIGN.md §12's frontend security checklist.

Run npx tsc --noEmit, npm run lint, npm run test, npm run build. Paste all four.
```

**Verify:** all four pass; `dist/index.d.ts` exists; no `any` on any request/response type;
`git diff --exit-code src/schema.d.ts` after re-running `generate:types` is clean; both basePath
keys (`dynamic_user`, `dynamic_user_admin`) are actually used somewhere in the hooks, not just
declared.

**Review for:** `react`/`@tanstack/react-query`/`@hjtdev/appkit` in `dependencies` instead of
`peerDependencies`; either manager or either config hook leaking through `index.ts`; a provider
being exported at all; any destructive/admin mutation hook firing on mount; the two key factories
accidentally sharing one root array (breaks the "invalidate only this surface" design).

### Phase 8 — Playground (two hosts)

The step that catches what generation and neither test suite can — and, uniquely for this app,
the step that proves the swappable-model story actually works end to end, not just in a unit test
against `tests.backend.settings_swapped`.

```
Phase 8: the playground — TWO minimal Django+Next hosts, not one, both under playground/.
docs/APP-DESIGN.md §11.2.

playground/default/ — this app installed with zero customization:
- backend/ — minimal Django project, dynamic_user in INSTALLED_APPS, AUTH_USER_MODEL =
  "dynamic_user.User" (the app's own concrete model, used as-is), pyproject.toml with
  [tool.uv.sources] path-editable to ../../../backend.
- frontend/ — minimal Next app, both basePaths wired, pages exercising every self-service hook
  plus a small admin panel page exercising every admin hook (seed a superuser and a plain staff
  user via a management command to demonstrate the ADMIN_REQUIRES_SUPERUSER distinction live).

playground/subclassed/ — proves a host CAN extend all three models:
- backend/ — a `core` app (per INTEGRATION-GUIDE.md's own convention) defining
  core.User(dynamic_user.AbstractDynamicUser) with one extra field, core.Profile/core.Setting
  the same way, AUTH_USER_MODEL/DYNAMIC_USER_PROFILE_MODEL/DYNAMIC_USER_SETTING_MODEL pointed at
  them, and DYNAMIC_USER["PROFILE_EDITABLE_FIELDS"] (etc.) including the extra field.
- frontend/ — same pages as playground/default, proving the extra field round-trips through a
  PATCH with zero changes to this app's own views/serializers — only settings and the host's own
  model file changed.

playground/docker-compose.yml — Postgres, Redis (celery extra path), and BOTH host stacks
(distinct ports), OR two compose files if that's cleaner — your call, document which and why in
this file's own header comment.

Bring both up and exercise every hook through the UI on both, and report on what only a live
round trip shows:
- does GET /me/ show locked fields as genuinely non-editable through the UI, on both hosts
- does the subclassed host's extra Profile field actually save and reload correctly
- does a public profile respect is_public on both hosts
- does the deletion-request flow work end to end: request -> admin review (as staff, as
  superuser, confirming ADMIN_REQUIRES_SUPERUSER's real effect) -> finalize (via the task/command,
  not just the forced admin endpoint) -> user row actually gone or anonymized per DELETION_MODE
- does a staff (non-superuser) admin's attempt to escalate a user to is_staff visibly fail in the
  admin UI, not just in a curl test
- does pagination work against more than one page of public profiles / admin users
- does the Jazzmin admin (default host) show the same data as the API path

Report any discrepancy and which half — or which host — is actually wrong.
```

**Verify:** the subclassed host's extra field round-trips through a real HTTP PATCH with no
code change to this app itself — this is the one test nothing else in the whole build can give
you, since Phase 4's unit test proves the factory but not a live server/client round trip.

### Phase 9 — README (the config block)

```
Phase 9: README.md. docs/APP-DESIGN.md §8 is the required structure — every section.

Fill it from what was actually built (code is the truth, not CONTRACT.md — report any
disagreement rather than papering over it). Include: installation (both halves) · compatibility ·
the two swappable-model settings (AUTH_USER_MODEL usage note, DYNAMIC_USER_PROFILE_MODEL,
DYNAMIC_USER_SETTING_MODEL — with a worked subclassing example lifted from
playground/subclassed/backend/core/models.py) · the DYNAMIC_USER settings block with every key
and its default · "no .env keys required" stated explicitly · URL mounting for BOTH urls.py and
urls_admin.py · migrations · signals table with exact payloads · services table with exact
signatures · mixins table (one row per mixin, fields it adds) · test helpers note (factory-boy in
the host's test group) · recommended periodic schedule for both tasks · suggested Jazzmin icons ·
frontend install and usage for BOTH basePath keys, with the two-provider-entries snippet shown
explicitly (a host easily misses that this app needs two `basePaths` entries, not one).

The settings/URL blocks must be copy-pasteable into a host with zero edits — verify by copying
them into BOTH playground hosts and confirming each still boots.

Then list every place README, CONTRACT.md, and the code disagree.
```

**Verify:** copying the README's blocks into fresh configs for both playground hosts, each still
boots.

### Phase 10 — CI, changelog, first release

```
Phase 10: CI and release.

1. Confirm django-dynamic-user (PyPI) and @hjtdev/django-dynamic-user (npm) are still free — this
   guide verified both at the time it was written; re-check before tagging, since time has
   passed.
2. README sync: backend/pyproject.toml readme = "README.md". Copy the finished README.md into
   backend/README.md and frontend/README.md verbatim. Add [project.urls] and package.json
   homepage/bugs pointing at github.com/HjtDev/django-dynamic-user.
3. .github/workflows/ci.yml — the caller from docs/APP-DESIGN.md §10.2, package-name:
   dynamic_user, coverage-threshold: 85, publish-npm: true, plus the publish-pypi job verbatim.
4. CHANGELOG.md — Keep a Changelog format, 1.0.0 entry covering everything built in Phases 0-9.
5. Verify version lockstep: backend/pyproject.toml, frontend/package.json, CHANGELOG.md all at
   1.0.0.
6. Walk docs/APP-DESIGN.md §9's security checklist item by item, with evidence. Give particular
   attention to: object-level permission checks (§5/§6's IDOR tests), "no secrets or keys
   hardcoded" (this app has none, say so explicitly), and the privilege-escalation guard from
   Phase 6 — re-run that test one more time here, fresh, as part of this walk rather than citing
   the earlier phase's result from memory.
7. Walk §12's frontend security checklist the same way — particular attention to every
   destructive/admin mutation hook (Phase 7's list) never firing on mount.
8. Register both trusted publishers before the first tag, per §10.2's steps 2-4.

Then give the exact commands to tag and push v1.0.0.
```

**Verify:** CI green on a PR; after the tag push, both registry pages show a real, non-empty
description — check directly, not from green CI alone.

### Phase 11 — Install it into a real host, twice

```
Phase 11: real-world verification. In a fresh clone of base-scaffold, install
django-dynamic-user at v1.0.0 following docs/INTEGRATION-GUIDE.md §2 — all steps, using only
README.md for configuration values, twice: once accepting every default model, once subclassing
all three the way playground/subclassed/ does. Don't use anything you know from building the
package.

Specifically confirm, on both runs: AUTH_USER_MODEL/DYNAMIC_USER_PROFILE_MODEL/
DYNAMIC_USER_SETTING_MODEL wired correctly, dynamic_user added to INSTALLED_APPS, both urls.py and
urls_admin.py mounted, no .env changes needed, the DYNAMIC_USER settings block copy-pasted as-is
boots cleanly, BOTH frontend basePaths entries wired (a host installing only one is a documented
failure mode, per this guide's own §4 table — confirm the README actually warns about it clearly
enough that this run catches the mistake before it's made), the Jazzmin sidebar entries appear
without further JAZZMIN_SETTINGS edits, and — on the second run only — the subclassed model's
extra field is reachable through a real PATCH with zero package-level code changes.

Report every step that didn't work as documented, every value the README omitted, and every place
you had to guess. Then fix the README.
```

Finally: add the app to the registry (`BASE-DESIGN.md` §11.3 / `ecosystem-docs/APPS.md`).

---

## 3. Prompt patterns for this app

The generic guide's boundary/host-perspective/version-impact questions all apply unchanged
(`CLAUDE-CODE-GUIDE-APP.md` §3) — run them at the end of Phases 3, 6, and 7. Three more, specific
to an app whose entire job is being safely subclassed while holding credentials:

> "List every place in this package that reads or writes `is_staff`, `is_superuser`, or
> `is_active`. For each, name the function and confirm a non-superuser request can never reach
> it, even indirectly through a partial-update body. If any path can, that's not a style issue —
> fix it before continuing."

> "List every place this package resolves the Profile or Setting model. For each, confirm it goes
> through `resolution.py` rather than a concrete import. Then imagine a host has swapped both
> models for its own subclasses — walk through what would break, and where."

> "Pick one setting from `DYNAMIC_USER`'s DEFAULTS. Change its value in `tests.backend.settings.py`
> only, run `makemigrations --check --dry-run`. If it reports anything, that setting is wired to a
> model class attribute instead of resolved at call time — find where and fix it."

## 4. Failure modes specific to this app

| Symptom | Cause | Guard |
|---|---|---|
| A host's subclassed Profile 500s on PATCH | Serializer built from a concrete `Profile` import instead of `resolution.get_profile_model()` | Phase 4's factory + the swapped-settings test suite run in every phase from 2 onward |
| Changing a field allowlist in settings produces a migration | A settings-driven value baked into a model `Meta`/field kwarg instead of resolved at call time | §3's "change one setting, run `makemigrations --check`" prompt |
| A staff (non-superuser) admin can make themselves a superuser | `CanEscalatePrivilege` missing on the admin `PATCH /users/{id}/` path | Phase 6's privilege-escalation test, tried against a temporarily-removed guard |
| A private profile's existence leaks via a 403 vs 404 difference | `GET /profiles/{id}/` returning 403 instead of 404 for a private profile a non-owner requests | Phase 5's private-profile test asserts the status code, not just "not 200" |
| `Profile`/`Setting` rows silently never get created | `AUTO_CREATE_PROFILE`/`AUTO_CREATE_SETTING` receiver never connected because `apps.py.ready()` didn't wire it, or wired it against the concrete model instead of the resolved one | Phase 3's auto-provisioning test run against the swapped settings module specifically |
| Admin frontend hooks silently 404 or hit the wrong prefix | Host wired only the `dynamic_user` basePath, forgot `dynamic_user_admin` | Phase 9's README shows both entries explicitly; Phase 11 installs and checks both |
| A rejected/finalized deletion request can be "finalized" again | `.finalize()` missing a status guard | Phase 3's test asserting `.finalize()` on a non-"approved" request raises |
| `password` (or a hash) shows up in an API response | A hand-written serializer, or a `fields` list fed to `build_serializer`, includes it | Phase 4's factory hard-refuses `password` regardless of what's requested; test asserts this |

## 5. Done means

Everything in `CLAUDE-CODE-GUIDE-APP.md` §7, plus:

- [ ] Every business-logic file resolves `Profile`/`Setting` through `resolution.py` — confirmed
      by the boundary question in §3, not assumed.
- [ ] A test proves a settings-only change produces zero migration diff.
- [ ] A test proves a non-superuser admin can never write `is_staff`/`is_superuser`/`is_active`,
      on any user, tried against a temporarily-removed guard.
- [ ] A test proves a private profile 404s (not 403) for a non-owner.
- [ ] The full test suite passes against **both** `tests.backend.settings` and
      `tests.backend.settings_swapped`, in every phase from 2 onward.
- [ ] `build_serializer()` is proven cached (identity, not equality) and proven to reject
      `password` even when explicitly requested.
- [ ] Playground Phase 8 proves the subclassed host's extra field round-trips over real HTTP with
      zero package-level code changes.
- [ ] Both frontend basePath keys (`dynamic_user`, `dynamic_user_admin`) documented and installed
      in Phase 11's real-host check.
- [ ] The account-deletion flow verified end to end — request, review (both admin postures),
      finalize via the task/command path, not only the forced admin endpoint.
