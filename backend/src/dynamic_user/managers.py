"""``UserManager`` — the manager ``AbstractBaseUser`` requires.

Phase 2 implements ``UserManager(BaseUserManager)``: ``create_user(username, email,
password=None, **extra)`` and ``create_superuser(username, email, password, **extra)``.

``create_superuser`` sets ``is_staff=True, is_superuser=True`` directly — this is the one place
in the whole package those fields are written outside a superuser-gated HTTP path, and it's safe
*because* it has no HTTP path at all: it's reachable only from ``createsuperuser``/a shell/a data
migration, never a request. Documented here so a later phase doesn't misread it as a violation of
this repo's ``CLAUDE.md`` rule 3 (no non-superuser-gated code path may write
``is_staff``/``is_superuser``/``is_active``).
"""
